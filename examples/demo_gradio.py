import os
import logging
from logging.handlers import RotatingFileHandler
import json
import tempfile
from datetime import datetime

import gradio as gr
from gradio_pdf import PDF
from dotenv import load_dotenv
from openai import OpenAI, AzureOpenAI
import pandas as pd

from pdf2aas.dictionary import Dictionary, CDD, ECLASS, ETIM, PropertyDefinition
from pdf2aas.preprocessor import PDFium
from pdf2aas.extractor import PropertyLLM, PropertyLLMSearch, CustomLLMClientHTTP, Property
from pdf2aas.generator import AASSubmodelTechnicalData, AASTemplate

logger = logging.getLogger(__name__)

load_dotenv()

def check_extract_ready(pdf_upload, definitions, dictionary):
    return gr.Button(interactive=
        pdf_upload is not None
        and (
            dictionary is None
            or (
                definitions is not None and
                len(definitions) > 1
                )
        )
    )

def get_class_choices(dictionary: Dictionary):
    if dictionary is None:
        return []
    if isinstance(dictionary, ECLASS):
        return [(f"{eclass.id} {eclass.name}", eclass.id) for eclass in dictionary.classes.values() if not eclass.id.endswith('00')]
    elif isinstance(dictionary, ETIM):
        return [(f"{etim.id.split('/')[0]} {etim.name}", etim.id) for etim in dictionary.classes.values()]
    return [(f"{class_.id} {class_.name}", class_.id) for class_ in dictionary.classes.values()]

def change_dictionary_type(dictionary_type):
    if dictionary_type == "ECLASS":
        dictionary = ECLASS()
    elif dictionary_type == "ETIM":
        dictionary = ETIM()
    elif dictionary_type == "CDD":
        dictionary = CDD()
    else:
        return (None,
            gr.update(visible=False, value=None),
            gr.update(visible=False, value=None),
            gr.update(visible=dictionary_type == "AAS", value=None)
        )
    return (
        dictionary,
        gr.update(choices=get_class_choices(dictionary), value=None, visible=True),
        gr.update(choices=dictionary.supported_releases, value=dictionary.release, visible=True),
        gr.update(visible=False, value=None),
    )

def change_dictionary_release(dictionary_type, release):
    if dictionary_type == "ECLASS":
        dictionary = ECLASS(release)
    elif dictionary_type == "ETIM":
        dictionary = ETIM(release)
    elif dictionary_type == "CDD":
        dictionary = CDD(release)
    else:
        return None, None
    dictionary.load_from_file()
    return dictionary, gr.Dropdown(choices=get_class_choices(dictionary))

def change_dictionary_class(dictionary, class_id):
    if class_id is None or dictionary is None:
        return None
    id_parsed = dictionary.parse_class_id(class_id)
    if id_parsed is None:
        gr.Warning(f"Class id has wrong format. Should be 8 digits for eclass (e.g. 27-27-40-01) or EC plus 6 digits for ETIM (e.g. EC002714).")
    return id_parsed

property_details_default_str = "## Select Property ID in Table for Details"

def get_class_property_definitions(
        class_id,
        dictionary,
    ):
    if class_id is None or dictionary is None:
        return None, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
    download = False
    if class_id not in dictionary.classes.keys():
        download = True
        gr.Info("Class not in dictionary file. Try downloading from website.", duration=3)
    definitions = dictionary.get_class_properties(class_id)
    class_info = dictionary.classes.get(class_id)
    if class_info:
        class_info = f"""# {class_info.name}
* ID: [{class_info.id}]({dictionary.get_class_url(class_info.id)})
* Definition: {class_info.description}
* Keywords: {', '.join(class_info.keywords)}
* Properties: {len(class_info.properties)}
"""
    if definitions is None or len(definitions) == 0:
        gr.Warning(f"No property definitions found for class {class_id} in release {dictionary.release}.")
        return (class_id,
            gr.update(visible=True, value=class_info),
            gr.update(visible=False),
            gr.update(visible=False)
        )
    if download:
        class_id = gr.update(choices=get_class_choices(dictionary))
        dictionary.save_to_file()

    definitions_df = pd.DataFrame([
        {
            'ID': definition.id,
            'Type': definition.type,
            'Name': definition.name.get('en'),
        }
        for definition in definitions
    ])

    return (class_id,
            gr.update(visible=True, value=class_info),
            gr.update(visible=True, value=definitions_df),
            gr.update(visible=True, value=property_details_default_str)
    )

def get_aas_template_properties(aas_template_upload):
    aas_template = AASTemplate(aas_template_upload)
    properties = aas_template.get_properties()
    if len(properties) == 0:
        gr.Warning("No properties found in aasx template.")
        return (
            aas_template,
            gr.update(visible=False),
            gr.update(visible=False)
        )

    properties_df = pd.DataFrame([
        {
            'ID': property_.id,
            'Label': property_.label,
            'Value': property_.value,
            'Unit': property_.unit
                if property_.unit is not None else property_.definition.unit
                if property_.definition is not None else None,
            'Description': property_.reference,
            'Definition': property_.definition_id,
        }
        for property_ in properties
    ])

    return (aas_template,
        gr.update(visible=True, value=properties_df),
        gr.update(visible=True, value=property_details_default_str)
    )

def select_property_info(dictionary_type: str, dictionary: Dictionary | None, aas_template: AASTemplate | None, evt: gr.SelectData):
    if dictionary is None and aas_template is None:
        return None

    #FIXME Currently this will get the wrong row, when the user has sorted the dataframe: https://github.com/gradio-app/gradio/pull/9128
    #Therefore, we only accept selection of the first row
    if evt.index[1] != 0:
        return property_details_default_str

    if dictionary_type == "AAS":
        property_ = aas_template.get_property(evt.value)
        if property_ is None:
            return property_details_default_str
        property_info = \
f"""## {property_.label}
* ID: {property_.id}
* Label: {property_.label}
* Value: {property_.value}
* Unit: {property_.unit}
* Description (Reference): {property_.reference}
* Language: {property_.language}
"""
        definition = property_.definition
        if definition is None:
            return property_info
        return property_info + \
f"""
### Definition
* ID: {property_.definition_id}
* Name: {property_.definition_name}
* Type: {definition.type}
* Definition: {definition.definition.get(property_.language, next(iter(definition.definition.values()), ''))}
* Unit: {definition.unit}
* Values:{"".join(["\n  * " +
        f"{v.get('value')} ({v.get('id')})"
        if isinstance(v, dict) else str(v)
        for v in property_.definition.values])}
"""
    else:
        definition = dictionary.get_property(evt.value)
        if definition is None:
            return property_details_default_str
    return \
f"""## {definition.name.get('en')}
* ID: [{definition.id.split('/')[0] if isinstance(dictionary, ETIM) else definition.id}]({dictionary.get_property_url(definition.id)})
* Type: {definition.type}
* Definition: {definition.definition.get('en', next(iter(definition.definition.values()), ''))}
* Unit: {definition.unit}
* Values:{"".join(["\n  * " +
        f"{v.get('value')} ({v.get('id')})"
        if isinstance(v, dict) else str(v)
        for v in definition.values])}
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
            headers=headers_json,
            verify=False if "REQUESTS_VERIFY_FALSE" in os.environ else None,
        )
    return None

def mark_extracted_references(datasheet, properties: list[Property]):
    for property_ in properties:
        reference = property_.reference
        if reference is None or len(reference.strip()) == 0:
            continue
    
        start = datasheet['text'].find(reference)
        if start == -1:
            start = datasheet['text'].replace('\n',' ').find(reference.replace('\n',' '))
        if start == -1:
            logger.info(f"Reference not found: {reference}")
            # TODO mark red in properties dataframe
            continue
        unit = f" [{property_.unit}]" if property_.unit else ''
        if property_.definition is None:
            name = property_.label
        else:
            name = f"{property_.definition_name} ({property_.definition_id})"
        datasheet['entities'].append({
            'entity': f"{name}: {property_.value}{unit}",
            'start': start,
            'end': start + len(reference)
        })

def properties_to_dataframe(properties: list[Property]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                'ID' : p.definition_id,
                'Name': p.label,
                'Value': p.value,
                'Unit': p.unit,
                'Reference': p.reference,
            }
            for p in properties
        ], columns=['ID', 'Name', 'Value', 'Unit', 'Reference']
    )

def extract(
        pdf_upload,
        class_id,
        dictionary,
        client,
        prompt_hint,
        model,
        batch_size,
        temperature,
        max_tokens,
        use_in_prompt,
        extract_general_information,
        max_definition_chars,
        max_values_length,
    ):

    if pdf_upload is None:
        yield None, None, None, None, None, gr.update(interactive=False)
        return
    preprocessor = PDFium()
    preprocessed_datasheet = preprocessor.convert(pdf_upload)
    if preprocessed_datasheet is None:
        raise gr.Error("Error while preprocessing datasheet.")
    datasheet_txt = {'text': "\n".join(preprocessed_datasheet), 'entities': []}
    yield None, None, datasheet_txt, None, None, gr.update()

    if dictionary is None:
        extractor = PropertyLLM(
            model_identifier=model,
            client=client,
        )
    else:
        extractor = PropertyLLMSearch(
            model_identifier=model,
            client=client,
            property_keys_in_prompt=use_in_prompt,
        )
    extractor.temperature = temperature
    extractor.max_tokens = max_tokens if max_tokens > 0 else None
    extractor.max_values_length = max_values_length
    extractor.max_definition_chars = max_definition_chars

    definitions = []
    if dictionary is not None:
        definitions = dictionary.get_class_properties(class_id)

    if extract_general_information:
        for property_ in AASSubmodelTechnicalData().general_information.value:
            if isinstance(dictionary, ECLASS) \
                    and any(d.id[10:16] == property_.semantic_id.key[0].value[10:16] for d in definitions):
                continue
            definitions.append(
                PropertyDefinition(
                    property_.semantic_id.key[0].value,
                    {'en': property_.id_short},
                    "string",
                    #TODO add description to submodel and get here (or from concept description)
                )
            )

    raw_results=[]
    raw_prompts=[]
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
    else:
        properties = []
        yield None, None, datasheet_txt, None, None, gr.update(interactive=True)
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
                yield properties, properties_to_dataframe(properties), datasheet_txt, raw_prompts, raw_results, gr.update()
    gr.Info('Extraction completed.', duration=3)
    yield properties, properties_to_dataframe(properties), datasheet_txt, raw_prompts, raw_results, gr.update(interactive=False)

def create_chat_history(raw_prompts, raw_results, client):
    if raw_prompts is None or len(raw_prompts) == 0:
        return []
    history = []
    for idx in range(len(raw_prompts)):
        history.extend(raw_prompts[idx])
        if idx < len(raw_results):
            if isinstance(client, CustomLLMClientHTTP):
                content = client.evaluate_result_path(raw_results[idx])
                if content is None:
                    continue
                answer = {'role': 'assistant', 'content': content}
            else:
                try:
                    answer = raw_results[idx]['choices'][0]['message']
                except KeyError:
                    continue
            history.append(answer)
    return history

def create_download_results(properties: list[Property], property_df: pd.DataFrame, tempdir, prompt_hint, model, temperature, batch_size, use_in_prompt, max_definition_chars, max_values_length, dictionary, class_id):
    if properties is None or len(properties) == 0:
        return None
    
    properties_path = os.path.join(tempdir.name, 'properties_extracted.json')
    property_df.to_json(properties_path, indent=2, orient='records')

    excel_path = os.path.join(tempdir.name, "properties_extracted.xlsx")
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        property_df.to_excel(
            writer,
            index=False,
            sheet_name='extracted',
            freeze_panes=(1, 1),
        )
        extracted_sheet = writer.sheets['extracted']
        extracted_sheet.auto_filter.ref = extracted_sheet.dimensions
        
        settings = writer.book.create_sheet('settings')
        settings.append(['prompt_hint', prompt_hint])
        settings.append(['model', model])
        settings.append(['temperature', temperature])
        settings.append(['batch_size', batch_size])
        settings.append(['use_in_prompt', " ".join(use_in_prompt)])
        settings.append(['max_definition_chars', max_definition_chars])
        settings.append(['max_values_length', max_values_length])
        settings.append(['dictionary_type', dictionary.name if dictionary is not None else ''])
        settings.append(['dictionary_release', dictionary.release if dictionary is not None else ''])
        settings.append(['dictionary_class', class_id])
    
    submodel_path = os.path.join(tempdir.name, 'technical_data_submodel.json')
    #TODO set identifier and other properties --> load from a template, that can be specified in settings?
    submodel = AASSubmodelTechnicalData()
    if dictionary is not None and class_id is not None:
        submodel.add_classification(dictionary, class_id)
    submodel.add_properties(properties)
    submodel.dump(submodel_path)

    aasx_path = os.path.join(tempdir.name, 'technical_data.aasx')
    submodel.save_as_aasx(aasx_path)

    submodel.remove_empty_submodel_elements()
    aasx_path_noneEmpty = os.path.join(tempdir.name, 'technical_data_withoutEmpty.aasx')
    submodel.save_as_aasx(aasx_path_noneEmpty)

    return [excel_path, properties_path, submodel_path, aasx_path, aasx_path_noneEmpty]

def init_tempdir():
    tempdir =  tempfile.TemporaryDirectory(prefix="pdf2aas_")
    logger.info(f"Created tempdir: {tempdir.name}")
    return tempdir

def main(debug=False, init_settings_path=None, share=False, server_port=None):

    with gr.Blocks(title="BaSys4Transfer PDF to AAS",analytics_enabled=False) as demo:
        dictionary = gr.State(value=None)
        client = gr.State()
        tempdir = gr.State(value=init_tempdir)
        extracted_properties = gr.State()
        aas_template = gr.State()
        
        with gr.Tab(label="Definitions"):
            with gr.Column():
                with gr.Row():
                    dictionary_type = gr.Dropdown(
                        label="Dictionary",
                        allow_custom_value=False,
                        scale=1,
                        choices=['None','ECLASS', 'ETIM', 'CDD', 'AAS'],
                        value='None'
                    )
                    dictionary_class = gr.Dropdown(
                        label="Class",
                        allow_custom_value=True,
                        scale=2,
                        visible=False,
                    )
                    dictionary_release = gr.Dropdown(
                        label="Release",
                        visible=False,
                    )
                    aas_template_upload = gr.File(
                        label="Upload AAS Template",
                        file_count='single',
                        file_types=['.aasx'],
                        visible=False,
                        scale=2,
                        height=80
                    )
                class_info = gr.Markdown(
                    value="# Class Info",
                    show_copy_button=True,
                    visible=False,
                )
                with gr.Row():
                    property_defintions = gr.DataFrame(
                        label="Property Definitions",
                        show_label=False,
                        headers=['ID', 'Type', 'Name'],
                        interactive=False,
                        scale=3,
                        visible=False,
                    )
                    property_info = gr.Markdown(
                        show_copy_button=True,
                        visible=False,
                    )

        with gr.Tab("Extract"):
            with gr.Column():
                with gr.Row():
                    pdf_upload = gr.File(
                        label="Upload PDF Datasheet",
                        scale=2,
                        file_count='single',
                        file_types=['.pdf'],
                    )
                    extract_button = gr.Button(
                        "Extract Technical Data",
                        interactive=False,
                        scale=2,
                    )
                    cancel_extract_button = gr.Button(
                        "Cancel Extraction",
                        variant="stop",
                        interactive=False,
                    )
                    results = gr.File(
                        label="Download Results",
                        scale=2,
                    )
                extracted_properties_df = gr.DataFrame(
                    label="Extracted Values",
                    headers=['ID', 'Name', 'Value', 'Unit', 'Reference'],
                    value=properties_to_dataframe([]),
                    interactive=False,
                    wrap=True,
                )
                with gr.Accordion("Preprocessed Datasheet with References", open=False):
                    with gr.Row():
                        datasheet_text_highlighted = gr.HighlightedText(
                            show_label=False,
                            combine_adjacent=True,
                        )
                        datasheet_preview = PDF(
                            label="Datasheet Preview",
                            interactive=False,
                        )

        with gr.Tab("Raw Results"):
            chat_history = gr.Chatbot(
                label="Chat History",
                type="messages",
            )
            with gr.Row():
                raw_prompts = gr.JSON(
                    label="Prompts",
                )
                raw_results = gr.JSON(
                    label="Results",
                )

        with gr.Tab(label="Settings"):
            with gr.Group("Extraction Setting"):
                prompt_hint = gr.Text(
                    label="Optional Prompt Hint",
                )
                batch_size = gr.Slider(
                    label="Batch Size",
                    minimum=0,
                    maximum=100,
                    step=1
                )
                extract_general_information = gr.Checkbox(
                    label="Extract General Information",
                    value=False,
                )
                use_in_prompt = gr.Dropdown(
                    label="Use in prompt",
                    choices=['definition','unit','datatype', 'values'],
                    multiselect=True,
                    value=['unit', 'datatype'],
                    scale=2,
                )
                max_definition_chars = gr.Number(
                    label="Max. Definition Chars",
                    value=0,
                )
                max_values_length = gr.Number(
                    label="Max. Values Length",
                    value=0,
                )
            with gr.Group("LLM Client"):
                with gr.Group():
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
                    endpoint = gr.Text(
                        label="Endpoint",
                        lines=1,
                    )
                    api_key = gr.Text(
                        label="API Key",
                        lines=1,
                        type='password'
                    )
                with gr.Group():
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
                with gr.Group():
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
            with gr.Group("LLM Settings"):
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
            with gr.Group():
                with gr.Row():
                    settings_save = gr.Button(
                        "Create Settings File"
                    )
                    settings_load = gr.UploadButton(
                        "Load Settings File"
                    )
                settings_file = gr.File(
                    label="Download Settings"
                )

        
        dictionary_type.change(
            fn=change_dictionary_type,
            inputs=dictionary_type,
            outputs=[dictionary, dictionary_class, dictionary_release, aas_template_upload],
            show_progress="hidden"
        )
        dictionary_release.change(
            fn=change_dictionary_release,
            inputs=[dictionary_type, dictionary_release],
            outputs=[dictionary, dictionary_class],
            show_progress="hidden"
        )
        gr.on(
            triggers=[dictionary_class.change, dictionary_release.change],
            fn=change_dictionary_class,
            inputs=[dictionary, dictionary_class],
            outputs=dictionary_class,
            show_progress="hidden"
        ).success(
            fn=get_class_property_definitions,
            inputs=[dictionary_class, dictionary],
            outputs=[dictionary_class, class_info, property_defintions, property_info],
            show_progress="minimal"
        )
        property_defintions.select(
            fn=select_property_info,
            inputs=[dictionary_type, dictionary, aas_template],
            outputs=[property_info],
            show_progress='hidden'
        )
        aas_template_upload.upload(
            fn=get_aas_template_properties,
            inputs=[aas_template_upload],
            outputs=[aas_template, property_defintions, property_info],
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

        pdf_upload.change(
            fn=lambda pdf: pdf,
            inputs=pdf_upload,
            outputs=datasheet_preview
        )

        gr.on(
            triggers=[pdf_upload.change, property_defintions.change],
            fn=check_extract_ready,
            inputs=[pdf_upload, property_defintions, dictionary],
            outputs=[extract_button]
        )
        extraction_started = extract_button.click(
            fn=extract,
            inputs=[pdf_upload, dictionary_class, dictionary, client, prompt_hint, model, batch_size, temperature, max_tokens, use_in_prompt, extract_general_information, max_definition_chars, max_values_length],
            outputs=[extracted_properties, extracted_properties_df, datasheet_text_highlighted, raw_prompts, raw_results, cancel_extract_button],
        )
        cancel_extract_button.click(fn=lambda : gr.Info("Cancel after next response from LLM."), cancels=[extraction_started])
        extraction_started.then(
            fn=create_download_results,
            inputs=[extracted_properties, extracted_properties_df, tempdir, prompt_hint, model, temperature, batch_size, use_in_prompt, max_definition_chars, max_values_length, dictionary, dictionary_class],
            outputs=[results]
        )
        raw_prompts.change(
            fn=create_chat_history,
            inputs=[raw_prompts, raw_results, client],
            outputs=chat_history,
        )

        settings_list = [
            dictionary_type,
            dictionary_release,
            prompt_hint,
            endpoint_type, model,
            endpoint, api_key,
            azure_deployment, azure_api_version,
            custom_llm_request_template, custom_llm_result_path, custom_llm_headers,
            temperature, max_tokens,
            batch_size, use_in_prompt, extract_general_information, max_definition_chars, max_values_length
        ]

        def save_settings(settings):
            settings_path = os.path.join(settings[tempdir].name, "settings.json")
            with open(settings_path, 'w') as settings_file:
                json.dump({
                    'date': str(datetime.now()),
                    'settings': {c.label: v for c, v in settings.items() if c != tempdir},
                }, settings_file, indent=2)
            return settings_path

        def load_settings(settings_file_path):
            try:
                settings = json.load(open(settings_file_path))
            except (json.JSONDecodeError, OSError, FileNotFoundError) as error:
                raise gr.Error(f"Couldn't load settings: {error}")

            updated_settings = {}
            for key, value in settings.get('settings').items():
                component = next((component for component in settings_list if component.label == key), None)
                if component is None:
                    gr.Warning(f"Unexpected setting key '{key}'. Value ignored: {value}")
                else:
                    updated_settings[component] = value
            logger.info(f"Loaded settings from {settings_file_path}")
            return updated_settings

        settings_load.upload(
            fn=load_settings,
            inputs=settings_load,
            outputs=settings_list,
        )
        try:
            demo.load(
                fn=load_settings,
                inputs=gr.File(init_settings_path, visible=False),
                outputs=settings_list,
            )
        except FileNotFoundError:
            logger.info(f"Initial settings file not found: {os.path.abspath(init_settings_path)}")
        except gr.exceptions.Error as error:
            logger.warning(f"Initial settings file not loaded: {error}")
        gr.on(
            triggers=[demo.load, settings_save.click, settings_load.upload],
            fn=save_settings,
            inputs={tempdir} | set(settings_list),
            outputs=settings_file
        )
    
    demo.queue(max_size=10)
    demo.launch(quiet=not debug, share=share, server_port=server_port)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Small webapp for toolchain pdfium + eclass / etim / cdd --> LLM --> xlsx / json / aasx')
    parser.add_argument('--settings', type=str, help="Load settings from file. Defaults to settings.json", default='settings.json')
    parser.add_argument('--port', type=str, help="Change server port (default 7860 if free)", default=None)
    parser.add_argument('--share', action="store_true", help="Allow to use webserver outside localhost, aka. public.")
    parser.add_argument('--debug', action="store_true", help="Print debug information.")
    args = parser.parse_args()

    file_handler = RotatingFileHandler('pdf-to-aas.log', maxBytes=1e6, backupCount=0, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setLevel(logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    logger = logging.getLogger()
    logger.addHandler(file_handler)

    main(args.debug, args.settings, args.share, args.port)