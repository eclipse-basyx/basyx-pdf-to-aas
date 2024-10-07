"""Generator to export comma separated values (CSV)."""
import csv
import io
import logging

from .core import Generator

logger = logging.getLogger(__name__)

class CSV(Generator):
    """Generator for comma separated values."""

    header = ["name", "property", "value", "unit", "id", "reference"]
    """
    list[str]: The header row for the CSV file, containing column names according to Property class.

    See also:
        :func:`pdf2aas.extractor.core.Property.to_legacy_dict()`

    """

    def dumps(self) -> str:
        r"""Dump the csv to a string.
        
        Uses semicolon as delimiter and \n as new line on default.
        """
        csv_str = io.StringIO()
        writer = csv.DictWriter(
            csv_str,
            fieldnames=self.header,
            extrasaction="ignore",
            quoting=csv.QUOTE_ALL,
            delimiter=";",
            lineterminator="\n",
        )
        writer.writeheader()
        for property_ in self._properties:
            writer.writerow(property_.to_legacy_dict())
        return csv_str.getvalue()
