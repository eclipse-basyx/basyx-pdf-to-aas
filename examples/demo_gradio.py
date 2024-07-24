import os
import logging
from datetime import datetime

import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI, AzureOpenAI
import pandas as pd

from pdf2aas.dictionary import ECLASS
from pdf2aas.preprocessor import PDFium
from pdf2aas.extractor import PropertyLLMOpenAI

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger()

load_dotenv()

def check_extract_ready(pdf_upload, definitions:pd.DataFrame, client):
    return gr.Button(
        interactive=
            pdf_upload is not None and
            definitions is not None and
            len(definitions) > 1 and
            client is not None
        )

def get_class_choices(dictionary: ECLASS):
    return [(f"{eclass.id} {eclass.name}", eclass.id) for eclass in dictionary.classes.values() if not eclass.id.endswith('00')]

def change_eclass_release(release):
    dictionary = ECLASS(release)
    dictionary.load_from_file()
    return dictionary, gr.Dropdown(choices=get_class_choices(dictionary))

def change_eclass_class(eclass_id):
    if eclass_id is None:
        return None
    eclass_id_parsed = ECLASS.parse_class_id(eclass_id)
    if eclass_id_parsed is None:
        gr.Warning(f"Class id has wrong format. Should be 8 digits, e.g. 27-27-40-01.")
    return eclass_id_parsed

def get_class_property_definitions(
        eclass_id,
        dictionary,
    ):
    if eclass_id is None:
        return None, None, None, None
    download = False
    if eclass_id not in dictionary.classes.keys():
        download = True
        gr.Info("ECLASS class not in dictionary file. Try downloading from website. This may take some time.")
    definitions = dictionary.get_class_properties(eclass_id)
    class_info = dictionary.classes.get(eclass_id)
    if class_info:
        class_info = f"# {class_info.name} ({class_info.id})\n* definition: {class_info.description}\n* keywords: {', '.join(class_info.keywords)}\n* properties: {len(class_info.properties)}"
    if definitions is None or len(definitions) == 0:
        gr.Warning(f"No property definitions found for class {eclass_id} in release {dictionary.release}.")
        return eclass_id, class_info, None, None
    if download:
        eclass_id = gr.update(choices=get_class_choices(dictionary))
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

    return eclass_id, class_info, definitions_df

def check_azure_fields_active(endpoint_type):
    return gr.update(visible=endpoint_type=="azure"), gr.update(visible=endpoint_type=="azure")

def get_from_var_or_env(var, env_keys):
    if var is not None and len(var.strip()) > 0:
        return var
    for key in env_keys:
        value = os.environ.get(key)
        if value and len(value.strip()) > 0:
            return value
    return None
        
def change_client(endpoint_type, endpoint, api_key, azure_deployment, azure_api_version):
    if len(endpoint.strip()) == 0:
        endpoint = None
    if endpoint_type == "openai":
        return OpenAI(
            api_key=get_from_var_or_env(api_key, ['OPENAI_API_KEY']),
            base_url=endpoint
        )
    elif endpoint_type == "azure":
        return AzureOpenAI(
            api_key=get_from_var_or_env(api_key, ['AZURE_OPENAI_API_KEY','OPENAI_API_KEY']),
            azure_endpoint=get_from_var_or_env(endpoint, ['AZURE_ENDPOINT']),
            azure_deployment=get_from_var_or_env(azure_deployment, ['AZURE_DEPLOYMENT']),
            api_version=get_from_var_or_env(azure_api_version, ['AZURE_API_VERSION'])
        )
    return None

def init_client():
    return OpenAI()

def extract(
        pdf_upload,
        eclass_id,
        dictionary,
        client,
        prompt_hint,
        model,
        batch_size,
        temperature,
        max_tokens,
        use_in_prompt,
        max_definition_chars,
        progress=gr.Progress()
    ):

    if pdf_upload is None:
        return None, None, None, None, None
    progress(0, desc="Preprocessing data sheet.")
    preprocessor = PDFium()
    preprocessed_datasheet = preprocessor.convert(pdf_upload)
    if preprocessed_datasheet is None:
        gr.Warning("Error while preprocessing datasheet.")
        logger.error(f"Preprocessed datasheet is none.")
        return None, None, None, None, None
    datasheet_txt = {'text': "\n".join(preprocessed_datasheet), 'entities': []}
    
    definitions = dictionary.get_class_properties(eclass_id)

    extractor = PropertyLLMOpenAI(
        model_identifier=model,
        property_keys_in_prompt=use_in_prompt,
        client=client,
    )
    extractor.temperature = temperature
    extractor.max_tokens = max_tokens if max_tokens > 0 else None
    extractor.max_definition_chars = max_definition_chars
    if isinstance(client, AzureOpenAI):
        extractor.response_format = None

    raw_results=[]
    raw_prompts=[]
    if batch_size <= 0:
        progress(0, desc=f"Extracting {len(definitions)} properties from datasheet with {len(preprocessed_datasheet)} {'pages' if isinstance(preprocessed_datasheet, list) else 'chars'}.")
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
        gr.Warning("No properties extracted or LLM result not parseable.")
        return None, None, datasheet_txt, raw_prompts, raw_results

    progress(1, desc=f"Postprocessing {len(properties)} extracted properties.")
    for property in properties:
        property_id = property.get('id')
        reference = property.get('reference')
        if property_id is None or reference is None or len(reference.strip()) == 0:
            continue
    
        start = datasheet_txt['text'].find(reference)
        if start == -1:
            start = datasheet_txt['text'].replace('\n',' ').find(reference.replace('\n',' '))
        if start == -1:
            logger.info(f"Reference not found: {reference}")
            # TODO mark red in properties dataframe
            continue
        unit = f" [{property.get('unit')}]" if property.get('unit') else ''
        datasheet_txt['entities'].append({
            'entity': f"{property.get('name','')} ({property_id}): {property.get('value','')}{unit}",
            'start': start,
            'end': start + len(reference)
        })
    dataframe = pd.DataFrame(properties)

    try:
        os.makedirs("temp/demo", exist_ok=True)
        excel_path = os.path.join("temp/demo", datetime.now().strftime("%Y-%m-%d_%H-%M-%S_extracted.xlsx"))
        dataframe.to_excel(
            excel_path,
            index=False,
            sheet_name='extracted',
            freeze_panes=(1,1)
        )
    except OSError as e:
        gr.Warning(f"Couldn't export excel: {e}")
        excel_path = None

    return dataframe, excel_path, datasheet_txt, raw_prompts, raw_results

def main():

    with gr.Blocks(title="BaSys4Transfer PDF to AAS") as demo:
        dictionary = gr.State(ECLASS())
        dictionary.value.load_from_file()
        client = gr.State()
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
                        endpoint_type = gr.Dropdown(
                            label="Endpoint Type",
                            choices=["openai", "azure"],
                            value="openai",
                            allow_custom_value=True
                        )
                        model = gr.Dropdown(
                            label="Model",
                            choices=["gpt-3.5-turbo", "gpt-4o", "gpt-4o-mini"],
                            value="gpt-4o-mini",
                            allow_custom_value=True
                        )
                    with gr.Row():
                        endpoint = gr.Text(
                            label="Endpoint",
                            lines=1,
                        )
                        api_key = gr.Text(
                            label="API Key",
                            lines=1,
                        )
                    with gr.Row():
                        azure_deployment = gr.Text(
                            label="Azure Deplyoment",
                            visible=False,
                            lines=1,
                        )
                        azure_api_version = gr.Text(
                            label="Azure API version",
                            visible=False,
                            lines=1,
                        )
                    with gr.Row():
                        temperature = gr.Slider(
                            label="Temperature",
                            minimum=0,
                            maximum=2,
                            step=0.1
                        )
                        max_tokens = gr.Number(
                            label="Max. Tokens",
                            value=0,
                        )
                    with gr.Row():
                        batch_size = gr.Slider(
                            label="Batch Size",
                            minimum=0,
                            maximum=100,
                            step=1
                        )
                        use_in_prompt = gr.Dropdown(
                            label="Use in prompt",
                            choices=['definition','unit','datatype', 'values'],
                            multiselect=True,
                            value='unit',
                        )
                        max_definition_chars = gr.Number(
                            label="Max. Definition / Values Chars",
                            value=0,
                        )
                with gr.Row():
                    extract_button = gr.Button(
                        "Extract Technical Data",
                        interactive=False
                    )
            with gr.Column():
                with gr.Row():
                    eclass_class = gr.Dropdown(
                        label="ECLASS Class",
                        allow_custom_value=True,
                        scale=2,
                        choices=get_class_choices(dictionary.value),
                    )
                    eclass_release = gr.Dropdown(
                        label="ECLASS Release",
                        choices=ECLASS.supported_releases,
                        value=dictionary.value.release
                    )
                eclass_class_info = gr.Markdown()
                property_defintions = gr.DataFrame(
                    label="Property Definitions",
                    headers=['id', 'name', 'type', 'definition', 'values'],
                    interactive=False,
                    # column_widths=['20%', '20%', '20%', '20%', '20%']
                )
        extracted_values = gr.DataFrame(
            label="Extracted Values",
            headers=['id', 'property', 'value', 'unit', 'reference', 'name'],
            col_count=(6, "fixed")
        )
        extracted_values_excel = gr.File(
            label="Extracted Values Export",
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
    
        eclass_release.change(
            fn=change_eclass_release,
            inputs=eclass_release,
            outputs=[dictionary, eclass_class]
        )
        gr.on(
            triggers=[eclass_class.change, eclass_release.change],
            fn=change_eclass_class,
            inputs=eclass_class,
            outputs=eclass_class
        ).success(
            fn=get_class_property_definitions,
            inputs=[eclass_class, dictionary],
            outputs=[eclass_class, eclass_class_info, property_defintions]
        )

        gr.on(
            triggers=[endpoint_type.change, endpoint.change, api_key.change, azure_deployment.change, azure_api_version.change],
            fn=change_client,
            inputs=[endpoint_type, endpoint, api_key, azure_deployment, azure_api_version],
            outputs=client
        )
        endpoint_type.change(
            fn=check_azure_fields_active,
            inputs=[endpoint_type],
            outputs=[azure_deployment, azure_api_version]
        )

        gr.on(
            triggers=[pdf_upload.change, property_defintions.change, client.change],
            fn=check_extract_ready,
            inputs=[pdf_upload, property_defintions, client],
            outputs=[extract_button]
        )
        extract_button.click(
            fn=extract,
            inputs=[pdf_upload, eclass_class, dictionary, client, prompt_hint, model, batch_size, temperature, max_tokens, use_in_prompt, max_definition_chars],
            outputs=[extracted_values, extracted_values_excel, datasheet_text_highlighted, raw_prompts, raw_results]
        )

    demo.launch()

if __name__ == "__main__":
    main()