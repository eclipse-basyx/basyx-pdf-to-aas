import os
import logging
import json


from dotenv import load_dotenv

from pdf2aas.dictionary import ECLASS
from pdf2aas.extractor import PropertyLLMSearch,CustomLLMClientHTTP
from pdf2aas.generator import CSV

logger = logging.getLogger(__name__)

# Load the .env file with openai API Key
load_dotenv()

def main(datasheet,class_id,output):
    datasheet_text=None

    with open(datasheet) as file:
        datasheet_text=file.read()
        logger.info(f"Loaded datasheet from: {datasheet}") 

    dictionary = ECLASS()
    dictionary.load_from_file()
    property_definitions = dictionary.get_class_properties(class_id)
    dictionary.save_to_file()

    #Format according to demo_gradio settings file expected
    settings=json.load(open('settings.json'))
    settings=settings["settings"]
    logger.info(f"Loaded settings")   

    client=CustomLLMClientHTTP(
            api_key=settings['API Key'],
            endpoint=settings['Endpoint'],
            request_template=settings["Custom LLM Request Template"],
            result_path=settings["Custom LLM Result Path"],
            headers=json.loads(settings["Custom LLM Headers"]),
            verify=False,#TODO Careful verify false by default
            )
    
    extractor = PropertyLLMSearch(
        settings['Model'], 
        client=client, 
        max_tokens=settings['Max. Tokens'],
        property_keys_in_prompt=['unit','datatype'],
        )
    
    batch_size=settings['Batch Size']

    if batch_size <= 0:
        properties = extractor.extract(datasheet_text, property_definitions)
    elif batch_size == 1:
        properties = [extractor.extract(datasheet_text, d) for d in property_definitions]
    else:
        properties = [] 
        for i in range(0, len(property_definitions), batch_size):
            properties.extend(extractor.extract(datasheet_text, property_definitions[i:i + batch_size]))
                        
    
    generator = CSV()
    generator.add_properties(properties)
    generator.dump(output)
    logger.info(f"Generated csv written to: {output}")   

  
if __name__ == '__main__':
    import argparse
    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(description='Process data sheet with Eclass class ID')
    
    # Add the required arguments
    parser.add_argument('data_sheet', type=str, help='Path to the CSV file of the data sheet')
    parser.add_argument('class_id', type=str, help='Eclass class ID')
    parser.add_argument('--output', type=str, help='Path to the output CSV file', default='output.csv')
    parser.add_argument('--debug', action="store_true", help="Print debug information.")
        
    # Parse the command-line arguments
    args = parser.parse_args()


    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    logger = logging.getLogger()

    main(args.data_sheet,args.class_id,args.output)
    