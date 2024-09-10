import csv
import io
import logging

from .core import Generator

logger = logging.getLogger(__name__)

class CSV(Generator):
    header = ["name", "property", "value", "unit", "id", "reference"]

    def dumps(self) -> str:
        csv_str = io.StringIO()
        writer = csv.DictWriter(
            csv_str,
            fieldnames=self.header,
            extrasaction="ignore",
            quoting=csv.QUOTE_ALL,
            delimiter=';',
            lineterminator='\n'
        )
        writer.writeheader()
        for property_ in self._properties:
            writer.writerow(property_.to_legacy_dict())
        return csv_str.getvalue()
