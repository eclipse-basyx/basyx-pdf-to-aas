import os
import logging
from logging.handlers import RotatingFileHandler
import json
import tempfile
from datetime import datetime
from typing import Literal

import gradio as gr
from gradio_pdf import PDF
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError, AzureOpenAI
import pandas as pd

from pdf2aas.model import PropertyDefinition, Property
from pdf2aas.dictionary import Dictionary, CDD, ECLASS, ETIM
import pdf2aas.preprocessor as preprocessor
from pdf2aas.extractor import PropertyLLM, PropertyLLMSearch, CustomLLMClientHTTP
from pdf2aas.generator import AASSubmodelTechnicalData, AASTemplate

logger = logging.getLogger(__name__)

load_dotenv()

def check_extract_ready(datasheet, definitions, dictionary, aas_template):
    return gr.Button(interactive=
        datasheet is not None and len(datasheet) > 0
        and (
            (dictionary is None and aas_template is None) # Search for all properties
            or (definitions is not None and len(definitions) > 1) # Search for definitions
        )
    )

def get_class_choices(dictionary: Dictionary):
    if dictionary is None:
        return []
    if isinstance(dictionary, ECLASS):
        return [(f"{eclass.id} {eclass.name}", eclass.id) for eclass in dictionary.classes.values() if not eclass.id.endswith('00')]
    elif isinstance(dictionary, ETIM):
        return [(f"{etim.id.split('/')[-1]} {etim.name}", etim.id) for etim in dictionary.classes.values()]
    return [(f"{class_.id} {class_.name}", class_.id) for class_ in dictionary.classes.values()]

def change_dictionary_type(dictionary_type):
    if dictionary_type in ["ECLASS", "ETIM", "CDD"]:
        yield (gr.update(),
                gr.update(visible=True),
                gr.update(visible=True),
                gr.update(visible=False),
                gr.update(visible=False)
            )
        if dictionary_type == "ECLASS":
            dictionary = ECLASS()
        elif dictionary_type == "ETIM":
            dictionary = ETIM()
        elif dictionary_type == "CDD":
            dictionary = CDD()
        yield (
            dictionary,
            gr.update(choices=get_class_choices(dictionary), value=None),
            gr.update(choices=dictionary.supported_releases, value=dictionary.release),
            gr.update(value=None),
            gr.update(value=None),
        )
    else:
        yield (None,
            gr.update(visible=False, value=None),
            gr.update(visible=False, value=None),
            gr.update(visible=dictionary_type == "AAS", value=None),
            gr.update(visible=dictionary_type == "AAS", value=None)
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
            'Name': definition.get_name('en'),
        }
        for definition in definitions
    ])

    return (class_id,
            gr.update(visible=True, value=class_info),
            gr.update(visible=True, value=definitions_df),
            gr.update(visible=True, value=property_details_default_str)
    )

def get_aas_template_properties(aas_template_upload, aas_template_filter):
    if aas_template_upload is None:
        return (
            None,
            gr.update(visible=False),
            gr.update(visible=False)
        )

    submodel_element_filter = None
    if aas_template_filter:
        def filter_property_path(element):
            id_ = AASTemplate._create_id_from_path(element)
            if any(s in id_ for s in aas_template_filter.split(',')):
                return True
            return False
        submodel_element_filter = filter_property_path

    aas_template = AASTemplate(
        aasx_path=aas_template_upload,
        submodel_element_filter=submodel_element_filter,
    )
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
    if dictionary_type == "AAS":
        if aas_template is None:
            return None
        property_ = aas_template.get_property(evt.row_value[0])
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
        for v in definition.values])}
"""
    else:
        if dictionary is None:
            return None
        definition = dictionary.get_property(evt.row_value[0])
        if definition is None:
            return property_details_default_str
    return \
f"""## {definition.name.get('en')}
* ID: [{definition.id}]({dictionary.get_property_url(definition.id)})
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
        try:
            client = OpenAI(
                api_key=get_from_var_or_env(api_key, ['OPENAI_API_KEY']),
                base_url=get_from_var_or_env(endpoint, ['OPENAI_BASE_URL'])
            )
        except OpenAIError as error:
            gr.Error(f"Couldn't create OpenAI client: {error}")
            return None
        return client
    elif endpoint_type == "azure":
        try:
            client = AzureOpenAI(
                api_key=get_from_var_or_env(api_key, ['AZURE_OPENAI_API_KEY','OPENAI_API_KEY']),
                azure_endpoint=get_from_var_or_env(endpoint, ['AZURE_ENDPOINT']),
                azure_deployment=get_from_var_or_env(azure_deployment, ['AZURE_DEPLOYMENT']),
                api_version=get_from_var_or_env(azure_api_version, ['AZURE_API_VERSION'])
            )
        except (OpenAIError, ValueError) as error:
            gr.Error(f"Couldn't create AzureOpenAI client: {error}")
            return None
        return client
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

def mark_extracted_references(datasheet:str | None, properties: list[Property]):
    if datasheet is None:
        return gr.update(visible=False, value=None)
    if properties is None:
        return gr.update(visible=True, value={"text": datasheet, "entities": []})
    entities = []
    for property_ in properties:
        reference = property_.reference
        if reference is None or len(reference.strip()) == 0:
            continue
    
        start = datasheet.find(reference)
        if start == -1:
            start = datasheet.replace('\n',' ').find(reference.replace('\n',' '))
        if start == -1:
            logger.info(f"Reference not found: {reference}")
            # TODO mark red in properties dataframe
            continue
        unit = f" [{property_.unit}]" if property_.unit else ''
        if property_.definition is None:
            name = property_.label
        else:
            name = f"{property_.definition_name} ({property_.definition.id.split('/')[-1]})"
        entities.append({
            'entity': f"{name}: {property_.value}{unit}",
            'start': start,
            'end': start + len(reference)
        })
    return gr.update(visible=True, value={"text": datasheet, "entities": entities})

def properties_to_dataframe(properties: list[Property], aas_template : AASTemplate | None = None) -> pd.DataFrame:
    properties_dict = []
    for property_ in properties:
        id_ = property_.definition_id
        if aas_template is not None and id_ is not None:
            original_property = aas_template.get_property(id_)
            if original_property is not None and  original_property.definition_id is not None:
                id_ = original_property.definition_id

        properties_dict.append({ 
            'ID' : id_,
            'Name': property_.label,
            'Value': property_.value,
            'Unit': property_.unit,
            'Reference': property_.reference,
        })
    return pd.DataFrame(properties_dict, columns=['ID', 'Name', 'Value', 'Unit', 'Reference'])

def preprocess_datasheet(datasheet, preprocessor_type, tempdir):
    pdf_preview = gr.update(visible=False, value=None)
    if datasheet is None:
        return pdf_preview, None
    
    if datasheet.lower().endswith(".pdf"):
        pdf_preview = gr.update(visible=True, value=datasheet)

        pre = None
        if preprocessor_type == "text":
            gr.Warning("Text preprocessor not suitable for PDFs. Falling back to PDFium.")
        elif preprocessor_type == "pdfplumber":
            pre = preprocessor.PDFPlumber()
        elif preprocessor_type.startswith("pdfplumber_table"):
            pre = preprocessor.PDFPlumberTable(output_format=preprocessor_type.split("_")[-1])
        elif preprocessor_type.startswith("pdf2htmlEx"):
            if preprocessor.PDF2HTMLEX.is_installed():
                pre = preprocessor.PDF2HTMLEX(
                    reduction_level=getattr(
                        preprocessor.ReductionLevel,
                        preprocessor_type.split("_")[-1].upper(),
                        preprocessor.ReductionLevel.STRUCTURE
                    ),
                    temp_dir = tempdir.name
                )
            else:
                gr.Warning("PDF2HTMLEX not installed in system. Falling back to PDFium.")
        if pre is None:
            pre = preprocessor.PDFium()
    else:
        if preprocessor_type not in ["auto", "text"]:
            gr.Warning(f"Preprocessor '{preprocessor_type}' not suitable for '{datasheet.split('.')[-1]}' files. Falling back to Text preprocessor.")
        pre = preprocessor.Text(encoding="utf-8")

    preprocessed_datasheet = pre.convert(datasheet)
    if preprocessed_datasheet is None:
        gr.Warning("Error while preprocessing datasheet.")
        return pdf_preview, None
    return pdf_preview, "\n".join(preprocessed_datasheet) if isinstance(preprocessed_datasheet, list) else preprocessed_datasheet

def extract(
        datasheet: str | None,
        class_id: str,
        dictionary: Dictionary | None,
        aas_template: AASTemplate | None,
        client: OpenAI | AzureOpenAI | CustomLLMClientHTTP | None,
        prompt_hint: str,
        model: str,
        batch_size: int,
        temperature: float,
        max_tokens: int,
        use_in_prompt: list[Literal["definition", "unit", "values", "datatype"]],
        extract_general_information: bool,
        max_definition_chars: int,
        max_values_length: int,
    ):

    if datasheet is None or len (datasheet) == 0:
        gr.Warning("Preprocessed datasheet is none or empty.")
        yield None, properties_to_dataframe([]), None, None, gr.update(interactive=False)
        return
    if client is None:
        gr.Warning("No or wrong client configured. Please update settings.")
        yield None, properties_to_dataframe([]), None, None, gr.update(interactive=False)
        return

    if dictionary is not None:
        definitions = dictionary.get_class_properties(class_id)
    elif aas_template is not None:
        definitions = aas_template.get_property_definitions()
    else:
        definitions = []

    if extract_general_information and aas_template is None:
        for property_ in AASSubmodelTechnicalData().general_information.value:
            if property_.semantic_id is None:
                continue
            if any(
                ECLASS.check_property_irdi(d.id)
                and d.id[10:16] == property_.semantic_id.key[0].value[10:16]
                for d in definitions
            ):
                continue
            definitions.append(
                PropertyDefinition(
                    property_.semantic_id.key[0].value,
                    {'en': property_.id_short},
                    "string",
                    #TODO add description to submodel and get here (or from concept description)
                )
            )

    if len(definitions) == 0:
        extractor = PropertyLLM(
            model_identifier=model,
            client=client,
        )
        gr.Info("Extracting all properties without definitions to search for.", duration=3)
    else:
        extractor = PropertyLLMSearch(
            model_identifier=model,
            client=client,
            property_keys_in_prompt=use_in_prompt,
        )
        gr.Info(f"Searching for {len(definitions)} properties.", duration=3)
        extractor.max_values_length = max_values_length
        extractor.max_definition_chars = max_definition_chars
        
    extractor.temperature = temperature
    extractor.max_tokens = max_tokens if max_tokens > 0 else None

    raw_results: list = []
    raw_prompts: list = []
    if batch_size <= 0:
        properties = extractor.extract(
            datasheet,
            definitions,
            raw_prompts=raw_prompts,
            prompt_hint=prompt_hint,
            raw_results=raw_results
        )
    else:
        properties = []
        yield None, properties_to_dataframe([]), None, None, gr.update(interactive=True)
        for chunk_pos in range(0, len(definitions), batch_size):
            if batch_size == 1:
                property_definition_batch: list[PropertyDefinition] | PropertyDefinition = definitions[chunk_pos]
            else:
                property_definition_batch = definitions[chunk_pos:chunk_pos+batch_size]
            extracted = extractor.extract(
                    datasheet,
                    property_definition_batch,
                    raw_results=raw_results,
                    prompt_hint=prompt_hint,
                    raw_prompts=raw_prompts)
            properties.extend(extracted)
            yield properties, properties_to_dataframe(properties, aas_template), raw_prompts, raw_results, gr.update()
    gr.Info('Extraction completed.', duration=3)
    yield properties, properties_to_dataframe(properties, aas_template), raw_prompts, raw_results, gr.update(interactive=False)

def cancel_extract():
    gr.Info("Canceled extraction.")
    return gr.update(interactive=False)

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
            elif isinstance(raw_results[idx], str):
                answer = {'role': 'assistant', 'content': raw_results[idx]}
            else:
                try:
                    answer = raw_results[idx]['choices'][0]['message']
                except KeyError:
                    continue
            history.append(answer)
    return history

def create_download_results(
        properties: list[Property],
        property_df: pd.DataFrame,
        tempdir,
        prompt_hint,
        model, temperature,
        batch_size,
        use_in_prompt,
        max_definition_chars,
        max_values_length,
        dictionary,
        class_id,
        aas_template: AASTemplate | None,
):
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
    
    if aas_template is None:
        submodel_path = os.path.join(tempdir.name, 'technical_data_submodel.json')
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
    else:
        aas_template.add_properties(properties)
        aasx_path = os.path.join(tempdir.name, os.path.basename(aas_template.aasx_path))
        aas_template.save_as_aasx(aasx_path)
        return [excel_path, properties_path, aasx_path]

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
        datasheet_text = gr.State()
        
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
                aas_template_filter = gr.Textbox(
                    label="Filter AAS template properties",
                    info="Enter part of id short path (ID) to select property definitions for extraction. Multi selection separated by comma.",
                    visible=False,
                )
                class_info = gr.Markdown(
                    value="# Class Info",
                    show_copy_button=True,
                    visible=False,
                )
                property_defintions = gr.DataFrame(
                    label="Property Definitions",
                    show_label=False,
                    headers=['ID', 'Type', 'Name'],
                    interactive=False,
                    scale=3,
                    visible=False,
                    max_height=500
                )
                property_info = gr.Markdown(
                    show_copy_button=True,
                    visible=False,
                )

        with gr.Tab("Extract"):
            with gr.Row():
                datasheet_upload = gr.File(
                    label="Upload Datasheet",
                    scale=2,
                    file_count='single',
                    file_types=['.pdf', 'text'],
                )
                with gr.Column():
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
                preprocessor_type = gr.Dropdown(
                    label="Preprocessor type",
                    choices=[
                        "auto", "pdfium",
                        "text",
                        "pdfplumber",
                        "pdfplumber_table", "pdfplumber_table_tsv", "pdfplumber_table_github", "pdfplumber_table_html",
                        "pdf2htmlEx", "pdf2htmlEx_pages", "pdf2htmlEx_divs", "pdf2htmlEx_text"
                    ],
                    value="auto",
                    multiselect=False,
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
                        allow_custom_value=False
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
            outputs=[dictionary, dictionary_class, dictionary_release, aas_template_upload, aas_template_filter],
        )
        dictionary_release.change(
            fn=change_dictionary_release,
            inputs=[dictionary_type, dictionary_release],
            outputs=[dictionary, dictionary_class],
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
        gr.on(
            triggers=[aas_template_upload.change, aas_template_filter.submit],
            fn=get_aas_template_properties,
            inputs=[aas_template_upload, aas_template_filter],
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

        gr.on(
            triggers=[datasheet_upload.change, preprocessor_type.change],
            fn=preprocess_datasheet,
            inputs=[datasheet_upload, preprocessor_type, tempdir],
            outputs=[datasheet_preview, datasheet_text]
        )

        gr.on(
            triggers=[datasheet_text.change, property_defintions.change],
            fn=check_extract_ready,
            inputs=[datasheet_text, property_defintions, dictionary, aas_template],
            outputs=[extract_button]
        )
        extraction_started = extract_button.click(
            fn=extract,
            inputs=[datasheet_text, dictionary_class, dictionary, aas_template, client, prompt_hint, model, batch_size, temperature, max_tokens, use_in_prompt, extract_general_information, max_definition_chars, max_values_length],
            outputs=[extracted_properties, extracted_properties_df, raw_prompts, raw_results, cancel_extract_button],
        )
        cancel_extract_button.click(
            fn=cancel_extract,
            outputs=cancel_extract_button,
            cancels=[extraction_started]
        )
        extraction_started.then(
            fn=create_download_results,
            inputs=[extracted_properties, extracted_properties_df, tempdir, prompt_hint, model, temperature, batch_size, use_in_prompt, max_definition_chars, max_values_length, dictionary, dictionary_class, aas_template],
            outputs=[results]
        )
        gr.on(
            triggers=[extracted_properties_df.change, datasheet_text.change],
            fn=mark_extracted_references,
            inputs=[datasheet_text, extracted_properties],
            outputs=datasheet_text_highlighted,
        )
        raw_prompts.change(
            fn=create_chat_history,
            inputs=[raw_prompts, raw_results, client],
            outputs=chat_history,
        )

        settings_list = [
            dictionary_type,
            dictionary_release,
            preprocessor_type,
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
        except gr.Error as error:
            logger.warning(f"Initial settings file not loaded: {error}")
        gr.on(
            triggers=[demo.load, settings_save.click, settings_load.upload],
            fn=save_settings,
            inputs={tempdir} | set(settings_list),
            outputs=settings_file
        ).then(
            fn=change_client,
            inputs=[endpoint_type, endpoint, api_key, azure_deployment, azure_api_version, custom_llm_request_template, custom_llm_result_path, custom_llm_headers],
            outputs=client
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

    file_handler = RotatingFileHandler('pdf-to-aas.log', maxBytes=int(1e6), backupCount=0, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setLevel(logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    logger = logging.getLogger()
    logger.addHandler(file_handler)

    main(args.debug, args.settings, args.share, args.port)