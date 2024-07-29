import os
import logging
from datetime import datetime
import json
import tempfile

import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI, AzureOpenAI
import pandas as pd

from pdf2aas.dictionary import ECLASS
from pdf2aas.preprocessor import PDFium
from pdf2aas.extractor import PropertyLLMOpenAI, CustomLLMClientHTTP

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger()

load_dotenv()

def check_extract_ready(pdf_upload, definitions):
    return gr.Button(
        interactive=
            pdf_upload is not None and
            definitions is not None and
            len(definitions) > 1
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
        return None, None, None, None, None
    download = False
    if eclass_id not in dictionary.classes.keys():
        download = True
        gr.Info("ECLASS class not in dictionary file. Try downloading from website. This may take some time.")
    definitions = dictionary.get_class_properties(eclass_id)
    class_info = dictionary.classes.get(eclass_id)
    if class_info:
        class_info = f"""# {class_info.name}
* ID: {class_info.id}
* Definition: {class_info.description}
* Keywords: {', '.join(class_info.keywords)}
* Properties: {len(class_info.properties)}
"""
    if definitions is None or len(definitions) == 0:
        gr.Warning(f"No property definitions found for class {eclass_id} in release {dictionary.release}.")
        return eclass_id, class_info, None, None, None
    if download:
        eclass_id = gr.update(choices=get_class_choices(dictionary))
        dictionary.save_to_file()

    definitions_df = pd.DataFrame([
        {
            'ID': definition.id,
            'Name': definition.name.get('en'),
            'Type': definition.type,
        }
        for definition in definitions
    ])

    return eclass_id, class_info, definitions_df, "Select Property in Table for Details"

def select_property_info(dictionary: ECLASS | None, definitions: pd.DataFrame | None, evt: gr.SelectData):
    if dictionary is None or definitions is None:
        return None
    definition = dictionary.get_property(definitions.iloc[evt.index[0], 0])
    if definition is None:
        return "Select Property for Details"
    return f"""## {definition.name.get('en')}
* ID: {definition.id}
* Type: {definition.type}
* Definition: {definition.definition.get('en')}
* Values:{"".join(["\n  * " + v.get("value") for v in definition.values])}
"""

def check_additional_client_settings(endpoint_type):
    azure = endpoint_type=="azure"
    custom = endpoint_type=="custom"
    return gr.update(visible=azure), gr.update(visible=azure), gr.update(visible=custom), gr.update(visible=custom), gr.update(visible=custom)

def get_from_var_or_env(var, env_keys):
    if var is not None and len(var.strip()) > 0:
        return var
    for key in env_keys:
        value = os.environ.get(key)
        if value and len(value.strip()) > 0:
            return value
    return None
        
def change_client(
        endpoint_type,
        endpoint,
        api_key,
        azure_deployment,
        azure_api_version,
        request_template,
        result_path,
        headers):
    if len(endpoint.strip()) == 0:
        endpoint = None
    if endpoint_type == "openai":
        return OpenAI(
            api_key=get_from_var_or_env(api_key, ['OPENAI_API_KEY']),
            base_url=get_from_var_or_env(endpoint, ['OPENAI_BASE_URL'])
        )
    elif endpoint_type == "azure":
        return AzureOpenAI(
            api_key=get_from_var_or_env(api_key, ['AZURE_OPENAI_API_KEY','OPENAI_API_KEY']),
            azure_endpoint=get_from_var_or_env(endpoint, ['AZURE_ENDPOINT']),
            azure_deployment=get_from_var_or_env(azure_deployment, ['AZURE_DEPLOYMENT']),
            api_version=get_from_var_or_env(azure_api_version, ['AZURE_API_VERSION'])
        )
    elif endpoint_type == "custom":
        headers_json = None
        try:
            headers_json = json.loads(headers)
        except json.JSONDecodeError:
            pass
        return CustomLLMClientHTTP(
            api_key=get_from_var_or_env(api_key, ['API_KEY','OPENAI_API_KEY', 'AZURE_OPENAI_API_KEY']),
            endpoint=get_from_var_or_env(endpoint, ['OPENAI_BASE_URL']),
            request_template=request_template,
            result_path=result_path,
            headers=headers_json
        )
    return None

def mark_extracted_references(datasheet, properties):
    for property in properties:
        property_id = property.get('id')
        reference = property.get('reference')
        if property_id is None or reference is None or len(reference.strip()) == 0:
            continue
    
        start = datasheet['text'].find(reference)
        if start == -1:
            start = datasheet['text'].replace('\n',' ').find(reference.replace('\n',' '))
        if start == -1:
            logger.info(f"Reference not found: {reference}")
            # TODO mark red in properties dataframe
            continue
        unit = f" [{property.get('unit')}]" if property.get('unit') else ''
        datasheet['entities'].append({
            'entity': f"{property.get('name','')} ({property_id}): {property.get('value','')}{unit}",
            'start': start,
            'end': start + len(reference)
        })

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
    ):

    if pdf_upload is None:
        return None, None, None, None
    preprocessor = PDFium()
    preprocessed_datasheet = preprocessor.convert(pdf_upload)
    if preprocessed_datasheet is None:
        gr.Warning("Error while preprocessing datasheet.")
        logger.error(f"Preprocessed datasheet is none.")
        return None, None, None, None
    datasheet_txt = {'text': "\n".join(preprocessed_datasheet), 'entities': []}

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
    definitions = dictionary.get_class_properties(eclass_id)
    if batch_size <= 0:
        properties = extractor.extract(
            preprocessed_datasheet,
            definitions,
            raw_prompts=raw_prompts,
            prompt_hint=prompt_hint,
            raw_results=raw_results
        )
        if properties is not None:
            mark_extracted_references(datasheet_txt, properties)
    else:
        properties = []
        for chunk_pos in range(0, len(definitions), batch_size):
            property_definition_batch = definitions[chunk_pos:chunk_pos+batch_size]
            extracted = extractor.extract(
                    preprocessed_datasheet,
                    property_definition_batch,
                    raw_results=raw_results,
                    prompt_hint=prompt_hint,
                    raw_prompts=raw_prompts)
            if extracted is not None:
                properties.extend(extracted)
                mark_extracted_references(datasheet_txt, extracted)
            yield pd.DataFrame(properties), datasheet_txt, raw_prompts, raw_results
    if properties is None or len(properties) == 0:
        gr.Warning("No properties extracted or LLM result not parseable.")
        return None, datasheet_txt, raw_prompts, raw_results
    return pd.DataFrame(properties), datasheet_txt, raw_prompts, raw_results

def create_extracted_properties_excel(properties, tempdir):
    excel_path = os.path.join(tempdir.name, "properties_extracted.xlsx")
    properties.to_excel(
        excel_path,
        index=False,
        sheet_name='extracted',
        freeze_panes=(1,1),
    )
    return excel_path

def save_settings(settings):
    tempdir = next(iter(settings)) # Assume tempdir is first element
    settings_path = os.path.join(tempdir.value.name, "settings.json")
    settings.pop(tempdir)
    with open(settings_path, 'w') as settings_file:
        json.dump({c.label: v for c, v in settings.items()}, settings_file, indent=2)
    return settings_path

def load_settings(settings_file_path):
    settings = json.load(open(settings_file_path)).values()
    return tuple(settings)

def main():

    with gr.Blocks(title="BaSys4Transfer PDF to AAS",analytics_enabled=False) as demo:     
        dictionary = gr.State(ECLASS())
        dictionary.value.load_from_file()
        client = gr.State()
        tempdir = gr.State(tempfile.TemporaryDirectory(prefix="pdf2aas_"))
        
        with gr.Tab(label="ECLASS"):
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
                with gr.Row():
                    property_defintions = gr.DataFrame(
                        label="Property Definitions",
                        show_label=False,
                        headers=['ID', 'Name', 'Type'],
                        interactive=False,
                        scale=3
                    )
                    eclass_property_info = gr.Markdown()

        with gr.Tab("Extract"):
            with gr.Row():
                with gr.Row():
                    pdf_upload = gr.File(
                        label="Upload PDF Datasheet"
                    )
                    extract_button = gr.Button(
                        "Extract Technical Data",
                        interactive=False
                    )
                    cancel_extract_button = gr.Button(
                        "Cancel Extraction",
                        variant="stop"
                    )

            extracted_values = gr.DataFrame(
                label="Extracted Values",
                headers=['id', 'property', 'value', 'unit', 'reference', 'name'],
                col_count=(6, "fixed")
            )
            extracted_values_excel = gr.File(
                label="Export Extracted Values",
            )
            datasheet_text_highlighted = gr.HighlightedText(
                label="Preprocessed Datasheet with References",
                combine_adjacent=True
            )
        with gr.Tab("Raw Results"):
            with gr.Row():
                raw_prompts = gr.JSON(
                    label="Prompts",
                )
                raw_results = gr.JSON(
                    label="Results",
                )

        with gr.Tab(label="Settings"):
            prompt_hint = gr.Text(
                label="Optional Prompt Hint",
            )
            with gr.Row():
                endpoint_type = gr.Dropdown(
                    label="Endpoint Type",
                    choices=["openai", "azure", "custom"],
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
                    type='password'
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
                custom_llm_request_template = gr.Text(
                    label="Custom LLM Request Template",
                    visible=False,
                )
                custom_llm_result_path = gr.Text(
                    label="Custom LLM Result Path",
                    visible=False,
                )
                custom_llm_headers = gr.Text(
                    label="Custom LLM Headers",
                    visible=False,
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
                settings_save = gr.DownloadButton(
                    "Save Settings"
                )
                settings_load = gr.UploadButton(
                    "Load Settings"
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
            outputs=[eclass_class, eclass_class_info, property_defintions, eclass_property_info]
        )
        property_defintions.select(
            fn=select_property_info,
            inputs=[dictionary, property_defintions],
            outputs=[eclass_property_info]
        )

        gr.on(
            triggers=[endpoint_type.change, endpoint.change, api_key.change, azure_deployment.change, azure_api_version.change, custom_llm_request_template.change, custom_llm_result_path.change, custom_llm_headers.change],
            fn=change_client,
            inputs=[endpoint_type, endpoint, api_key, azure_deployment, azure_api_version, custom_llm_request_template, custom_llm_result_path, custom_llm_headers],
            outputs=client
        )
        endpoint_type.change(
            fn=check_additional_client_settings,
            inputs=[endpoint_type],
            outputs=[azure_deployment, azure_api_version, custom_llm_request_template, custom_llm_result_path, custom_llm_headers]
        )

        gr.on(
            triggers=[pdf_upload.change, property_defintions.change],
            fn=check_extract_ready,
            inputs=[pdf_upload, property_defintions],
            outputs=[extract_button]
        )
        extraction_started = extract_button.click(
            fn=extract,
            inputs=[pdf_upload, eclass_class, dictionary, client, prompt_hint, model, batch_size, temperature, max_tokens, use_in_prompt, max_definition_chars],
            outputs=[extracted_values, datasheet_text_highlighted, raw_prompts, raw_results],
        )
        cancel_extract_button.click(fn=lambda : gr.Info("Cancel after next response from LLM."), cancels=[extraction_started])
        extracted_values.change(
            fn=create_extracted_properties_excel,
            inputs=[extracted_values, tempdir],
            outputs=[extracted_values_excel]
        )

        settings_save.click(
            fn=save_settings,
            inputs={tempdir,
                    prompt_hint,
                    endpoint_type, model,
                    endpoint, api_key,
                    azure_deployment, azure_api_version,
                    custom_llm_request_template, custom_llm_result_path, custom_llm_headers,
                    temperature, max_tokens,
                    batch_size, use_in_prompt, max_definition_chars},
            outputs=settings_save
        )
        settings_load.upload(
            fn=load_settings,
            inputs=settings_load,
            outputs=[prompt_hint,
                    endpoint_type, model,
                    endpoint, api_key,
                    azure_deployment, azure_api_version,
                    custom_llm_request_template, custom_llm_result_path, custom_llm_headers,
                    temperature, max_tokens,
                    batch_size, use_in_prompt, max_definition_chars],
        )
    demo.launch()

if __name__ == "__main__":
    main()