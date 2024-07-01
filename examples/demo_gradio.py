import os
import logging
import re
import json

import gradio as gr
from gradio_pdf import PDF
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import openai
import pandas as pd

from pdf2aas.dictionary import ECLASS, dictionary_serializer
from pdf2aas.preprocessor import PDFium
from pdf2aas.extractor import PropertyLLMOpenAI

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger()

load_dotenv()

def get_class_property_definitions(
        eclass_id,
        eclass_release,
        pdf_upload,
        progress=gr.Progress()
    ):
    if eclass_id is None:
        #TODO try to get id from pdf_upload
        return None, None
    eclass_id = re.sub('[-_]', '', eclass_id.strip())
    dictionary = ECLASS(eclass_release)
    progress(0.5, desc=f"Loading ECLASS definitions for {eclass_id} in release {dictionary.release}")
    dictionary.load_from_file()
    definitions = dictionary.get_class_properties(eclass_id)
    if definitions is None or len(definitions) == 0:
        return None, None
    dictionary.save_to_file()

    definitions_df = pd.DataFrame([
        {
            'id': definition.id,
            'name': definition.name.get('en'),
            'type': definition.type,
            'defintion': definition.definition.get('en'),
            'values': [v.get("value") for v in definition.values]
        }
        for definition in definitions
    ])

    return eclass_id, definitions, definitions_df

def extract(
        pdf_upload,
        definitions,
        prompt_hint,
        endpoint,
        model,
        api_key,
        batch_size,
        temperature,
        use_in_prompt,
        progress=gr.Progress()
    ):

    if pdf_upload is None:
        return None, None, None, None
    progress(0, desc="Preprocessing data sheet.")
    preprocessor = PDFium()
    preprocessed_datasheet = preprocessor.convert(pdf_upload)
    if preprocessed_datasheet is None:
        logger.error(f"Preprocessed datasheet is none.")
        return None, None, None, None
    datasheet_txt = {'text': "\n".join(preprocessed_datasheet), 'entities': []}
    
    if definitions is None or len(definitions) == 0:
        return None, datasheet_txt, None, None

    if endpoint == "openai":
        if api_key == None or len(api_key.strip()) == 0:
            api_key = os.environ.get('OPENAI_API_KEY')
        if api_key == None or len(api_key.strip()) == 0:
            return None, datasheet_txt, None, None
        endpoint=None
        client= openai.Client(api_key=api_key)
    extractor = PropertyLLMOpenAI(
        model_identifier=model,
        api_endpoint=endpoint,
        property_keys_in_prompt=use_in_prompt,
        client=client
    )
    extractor.temperature = temperature

    raw_results=[]
    raw_prompts=[]
    if batch_size <= 0:
        progress(0.5, desc=f"Extracting {len(definitions)} properties from datasheet with {len(preprocessed_datasheet)} pages/chars.")
        properties = extractor.extract(
            preprocessed_datasheet,
            definitions,
            raw_prompts=raw_prompts,
            prompt_hint=prompt_hint,
            raw_results=raw_results
        )
    else:
        properties = []
        for chunk_pos in range(0, len(definitions), batch_size):
            #TODO allow stop extraction
            property_definition_batch = definitions[chunk_pos:chunk_pos+batch_size]
            progress((chunk_pos, len(definitions)),
                     unit='properties',
                     desc=f"Extracting {len(property_definition_batch)} properties from datasheet with {len(preprocessed_datasheet)} pages/chars.")
            extracted = extractor.extract(
                    preprocessed_datasheet,
                    property_definition_batch,
                    raw_results=raw_results,
                    prompt_hint=prompt_hint,
                    raw_prompts=raw_prompts)
            if extracted is None:
                continue
            properties.extend(extracted)
    if properties is None or len(properties) == 0:
        return None, datasheet_txt, raw_prompts, raw_results

    progress(1, desc=f"Postprocessing {len(properties)} extracted properties.")
    for property in properties:
        property_id = property.get('id')
        reference = property.get('reference')
        if property_id is None or reference is None or len(reference.strip()) == 0:
            continue
    
        start = datasheet_txt['text'].find(reference)
        if start == -1:
            logger.info(f"Reference not found: {reference}")
            continue
        unit = f" [{property.get('unit')}]" if property.get('unit') else ''
        datasheet_txt['entities'].append({
            'entity': f"{property.get('name','')} ({property_id}): {property.get('value','')}{unit}",
            'start': start,
            'end': start + len(reference)
        })
    return pd.DataFrame(properties), datasheet_txt, raw_prompts, raw_results


def main():

    with gr.Blocks(title="BaSys4Transfer PDF to AAS") as demo:
        property_defintions_list = gr.State()
        with gr.Row():
            with gr.Column():
                pdf_upload = gr.File(
                    label="Upload PDF Datasheet"
                )
                with gr.Accordion(label="Settings", open=False):
                    prompt_hint = gr.Text(
                        label="Optional Prompt Hint",
                    )
                    with gr.Row():
                        endpoint = gr.Dropdown(
                            label="Endpoint Type",
                            choices=["openai", "azure", "input"],
                            value="openai",
                            allow_custom_value=True
                        )
                        model = gr.Dropdown(
                            label="Model",
                            choices=["gpt-3.5-turbo", "gpt-4o"],
                            value="gpt-3.5-turbo",
                            allow_custom_value=True
                        )
                    api_key = gr.Text(
                        label="API Key",
                    )
                    with gr.Row():
                        batch_size = gr.Slider(
                            label="Batch Size",
                            minimum=0,
                            maximum=100,
                            step=1
                        )
                        temperature = gr.Slider(
                            label="Temperature",
                            minimum=0,
                            maximum=2,
                            step=0.1
                        )
                    use_in_prompt = gr.Dropdown(
                        label="Use in prompt",
                        choices=['definition','unit','datatype', 'values'],
                        multiselect=True,
                        value='unit'
                    )
                with gr.Row():
                    extract_button = gr.Button("Extract Technical Data")
            with gr.Column():
                with gr.Row():
                    eclass_class = gr.Dropdown(
                        label="ECLASS Class",
                        allow_custom_value=True,
                        scale=2
                    )
                    eclass_release = gr.Dropdown(
                        label="ECLASS Release",
                        choices=["14.0", "13.0", "12.0", "11.1", "11.0", "10.1", "10.0.1", "9.1", "9.0", "8.1", "8.0", "7.1", "7.0", "6.2", "6.1", "5.1.4"],
                        value="14.0"
                    )
                property_defintions = gr.DataFrame(
                    label="Property Definitions",
                    headers=['id', 'name', 'type', 'definition', 'values'],
                    # column_widths=['20%', '20%', '20%', '20%', '20%']
                )
        extracted_values = gr.DataFrame(
            label="Extracted Values",
            headers=['id', 'property', 'value', 'unit', 'reference', 'name'],
            col_count=(6, "fixed")
        )
        datasheet_text_highlighted = gr.HighlightedText(
            label="Preprocessed Datasheet with References"
        )
        with gr.Row():
            raw_prompts = gr.JSON(
                label="Raw Prompts",
            )
            raw_results = gr.JSON(
                label="Raw Results",
            )
    
        )
    
        extract_button.click(
            fn=extract,
            inputs=[pdf_upload, property_defintions_list, prompt_hint, endpoint, model, api_key, batch_size, temperature, use_in_prompt],
            outputs=[extracted_values, datasheet_text_highlighted, raw_prompts, raw_results]
        )

        eclass_class.change(
            fn=get_class_property_definitions,
            inputs=[eclass_class, eclass_release, pdf_upload],
            outputs=[eclass_class, property_defintions_list, property_defintions]
        )
        eclass_release.change(
            fn=get_class_property_definitions,
            inputs=[eclass_class, eclass_release, pdf_upload],
            outputs=[eclass_class, property_defintions_list, property_defintions]
        )

    demo.launch()

if __name__ == "__main__":
    main()