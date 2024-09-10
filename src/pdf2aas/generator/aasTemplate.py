import logging
import json

from basyx.aas import model
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer, AASXWriter, AASXReader
from basyx.aas.adapter.json import json_serialization

from .core import Generator
from ..extractor import Property

logger = logging.getLogger(__name__)

class AASTemplate(Generator):
    def __init__(
        self,
        aasx_path: str,
    ) -> None:
        self.aasx_path = aasx_path
        self.reset()

    def reset(self):
        self.object_store = model.DictObjectStore()
        self.file_store = DictSupplementaryFileContainer()
        try:
            with AASXReader(self.aasx_path) as reader:
                reader.read_into(self.object_store, self.file_store)
        except (ValueError, OSError):
            pass

    def add_properties(self, properties: list[Property]):
        ...

    def get_properties(self) -> list[Property]:
        return []

    def dumps(self):
        return json.dumps([o for o in self.object_store], cls=json_serialization.AASToJsonEncoder, indent=2)

    def save_as_aasx(self, filepath: str):
        with AASXWriter(filepath) as writer:
            writer.write_aas(
                aas_ids=[aas.id for aas in self.object_store if isinstance(aas, model.AssetAdministrationShell)],
                object_store=self.object_store,
                file_store=self.file_store,
                write_json=True)
