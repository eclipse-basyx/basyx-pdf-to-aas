# PDF to AAS

Python libraries and scripts to extract technical data from PDFs utilizing Transformers and especially **Large Language Models (LLMs)** to format them in an **Asset Administration Shell (AAS)** submodel.

## Workflow

```mermaid
flowchart LR
    datasheet(Data Sheet)
    dict[("Property 
                 Dictionary")]
    llm{{LLM}}
    submodel(AAS Submodel)
    table(Table)

    preprocessor[[Preprocessor]]
    dictProcessor[[Dictionary]]
    propertyExtractor[[Extractor]]
    generator[[Generator]]

    datasheet --pdf---> preprocessor --text--> propertyExtractor

    datasheet -.classification.-> dictProcessor
    dict --"class and
    property definition"---> dictProcessor --"property 
        definitions"
        -->  propertyExtractor

    propertyExtractor --prompt--> llm --property--> propertyExtractor
    propertyExtractor --property list--> generator

    generator --json--> submodel
    generator --csv, json--> table
```

Remarks:

* Typical *Property Dictionaries* are ECLASS, CDD, ETIM, EDIBATEC, EPIC, GPC, UniClass
* The *classification* (e.g. ECLASS or ETIM class of the device) will be done manualy first, but can be automated (e.g. also via LLMs) in the future
* Additional *PDF Preprocessors* might be added in the future, e.g. specialized on table or image extraction.
LLMs might also be used to preprocess the PDF content first, e.g. summarize it in JSON format

## Modules

* **preprocessor**: converts the PDF to a text format that can be processed by LLMs, keeping layout and table information.
  * **PDF2HTML**: Uses [pdf2htmlEX](https://github.com/pdf2htmlEX/pdf2htmlEX) to convert the PDF data sheets to HTML.
    The converted html is preprocessed further to reduce token usage for the llms.
  * **PDFium**: Uses [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) based on PDFium to extract text from pdf without layout information
* **dictionary**: defines classes and properties semantically.
  * **ECLASS**: downloads property definitions from [ECLASS website](https://eclass.eu/en/eclass-standard/search-content) for a given ECLASS class.
  * **ETIM**: downloads property definitions from [ETIM model releases](https://www.etim-international.com/downloads/?_sft_downloadcategory=model-releases) or via the [ETIM API](https://etimapi.etim-international.com/)
* **extractor**: extracts technical properties from the preprocessed data sheet.
  * **PropertyLLM**: Uses an LLM to search and extract a single property value with its unit from the given text.
* **generator**: transforms an extracted property-value list into different formats.
  * **TechnicalDataSubmodel**: outputs the properties in a [technical data submodel](https://github.com/admin-shell-io/submodel-templates/tree/main/published/Technical_Data/1/2).
  * **CSV**: outputs the properties as csv file

## Setup

* Create virtual environment (venv) in current directory with `python -m venv .venv`
* Activate venv
  * Windows: `.venv/Scripts/activate`
  * Linux: `source .venv/bin/activate`
* Install requirements
  * if you just want to use the project use `python -m pip install -r requirements.txt`
  * if you want to test it use `python -m pip install -r dev-requirements.txt`
* Install the PDF2AAS package as editable package with `python -m pip install -e .` This makes the package importable in the entire local system while remaining editable.
* For [pdf2htmlEX preprocessor](pdf2aas/preprocessor/pdf2htmlEX.py) the binary needs to be [downloaded](https://github.com/pdf2htmlEX/pdf2htmlEX/wiki/Download) and installed. Currently it is only available for Linux distributions, but it can be used via WSL or Docker on Windows.
* To run the GPT models via the OpenAI API an API key needs to be set as environment variable `OPENAI_API_KEY` or via `.env` file and the `python-dotenv` package.
* To run a local model, the extractor needs to be initialised or configured with an openai API conform api_endpoint.

Example using default toolchain (results in csv):

```py
from pdf2aas import PDF2AAS

pdf2aas = PDF2AAS()
result = pdf2aas.convert('path/to/datasheet.pdf', 'eclass id, e.g. 27274001')
print(result)
```

## Examples

You can find some example toolchains with intermediate steps in the [examples](examples/) folder.
To run them make sure PDF2AAS is installed according to [setup section above](#setup).
Then execute from this directory for example: `python examples/dummy.py`
Use `-h` or `--help` argument for more information on command line arguments.

## Tests

* If not already done, install the dev dependencies via `python -m pip install -r dev-requirements.txt`
* Run tests with `pytest`

## Evaluation

To evaluate the extraction process we will use existing manufacturer catalogs, e.g. from WAGO.

```mermaid
flowchart
    testset(Testset)
    stats(Statistic)

    subgraph eval [Evaluator]
      man[Manufacturer]
      
      dict[("Property
            Dictionary")]

      datasheet(Data Sheet)
      man_submodel(AAS Submodel)

      pdf2aas[[PDF to AAS]]
      comp[[Comparator]]
      download[[Downloader]]
      download[[Downloader]]

      man --> download --> datasheet & man_submodel

      dict --"class and
              property definition"--> pdf2aas

      datasheet --pdf--> pdf2aas
      man_submodel -.classification.-> pdf2aas
      
      pdf2aas --json--> comp
      man_submodel --json--> comp
    end
    
    testset --> eval --> stats
```
