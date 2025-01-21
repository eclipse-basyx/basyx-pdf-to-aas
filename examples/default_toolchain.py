import logging

from dotenv import load_dotenv

from pdf2aas import PDF2AAS

logger = logging.getLogger(__name__)

# Load the .env file with openai API Key
load_dotenv()

def main(datasheet, eclass_class_id, batch_size, output_path):
    PDF2AAS(batch_size=batch_size).convert(datasheet, eclass_class_id, output_path)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Example for toolchain pdfium/text + eclass --> LLM --> aas-submodel-technical-data')
    parser.add_argument('eclass', type=str, help="ECLASS class id in number format, e.g. 27274001.")
    parser.add_argument('datasheet', type=str, help="File path to PDF datasheet or text file.")
    parser.add_argument('--batch_size', type=int, help="How many properties should be extracted per LLM request. All in one prompt = 0. One request per Property < 0.", default=0)
    parser.add_argument('--output', type=str, help="Filepath for the technical data submodel json file that is produced.", default='technical-data-submodel.json')
    parser.add_argument('--debug', action="store_true", help="Print debug information.")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    logger = logging.getLogger()
    
    main(args.datasheet, args.eclass, args.batch_size, args.output)
