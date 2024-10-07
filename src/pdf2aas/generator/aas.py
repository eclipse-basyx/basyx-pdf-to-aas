"""Utility functions and variables for AAS generators."""
import logging
import re

from basyx.aas import model
from basyx.aas.model import datatypes

from ..extractor import Property
from ..dictionary import PropertyDefinition

logger = logging.getLogger(__name__)

anti_alphanumeric_regex = re.compile(r'[^a-zA-Z0-9]')

def cast_property(
        value,
        definition: PropertyDefinition
    ) -> model.ValueDataType:
    """Cast a value to an XSD DataType from the AAS module.
    
    Uses the definition.type if given and type() casts to find the type.
    Currently only Boolean, String, Integer and Float target types are supported.
    """
    if value is None:
        return None
    if definition is not None:
        match definition.type:
            case 'bool':
                return datatypes.Boolean(value)
            case 'numeric' | 'range':
            # Range should be catched using cast_range and should not be reached here
                try:
                    casted = float(value)
                except (ValueError, TypeError):
                    return datatypes.String(value)
                if casted.is_integer():
                    casted = int(casted)
                    return datatypes.Integer(casted)
                return datatypes.Float(casted)
            case 'string':
                return datatypes.String(value)
    
    if isinstance(value, bool):
        return datatypes.Boolean(value)
    if isinstance(value, int):
        return datatypes.Integer(value)
    if isinstance(value, float):
        if value.is_integer():
            return datatypes.Integer(value)
        return datatypes.Float(value)
    return datatypes.String(value)

def cast_range(property_: Property):
    """Cast a Property value to a Float or Integer XSD type as range.

    Relies on :meth: pdf2aas.extractor.core.Property.parse_numeric_range().
    
    Returns the min, max and the datatype (Float, Integer). If the cast is not
    successful, None for the min/max and String for the datytype is returned.
    """
    min, max = property_.parse_numeric_range()
    if isinstance(min, float) or isinstance(max, float):
        return None if min is None else float(min), None if max is None else float(max), datatypes.Float
    if isinstance(min, int) or isinstance(max, int):
        return None if min is None else int(min), None if max is None else int(max), datatypes.Integer
    else:
        return None, None, datatypes.String # XSD has no equivalent to None
    
def get_dict_data_type_from_xsd(datatype: model.DataTypeDefXsd):
    """Map XSD DataType to None, "bool", "numeric" or "string".
    
    These datatypes are mapped to string: Duration, DateTime, Date, Time, GYearMonth, GYear, GMonthDay, GMonth, GDay, Base64Binary, HexBinary,  AnyURI, String, NormalizedString.
    """
    if datatype is None:
        return None
    if datatype == datatypes.Boolean:
        return "bool"
    if datatype in [
            datatypes.Float,
            datatypes.Double,
            datatypes.Decimal,
            datatypes.Integer,
            datatypes.Long,
            datatypes.Int,
            datatypes.Short,
            datatypes.Byte,
            datatypes.NonPositiveInteger,
            datatypes.NegativeInteger,
            datatypes.NonNegativeInteger,
            datatypes.PositiveInteger,
            datatypes.UnsignedLong,
            datatypes.UnsignedInt,
            datatypes.UnsignedShort,
            datatypes.UnsignedByte
            ]:
        return "numeric"
    # Duration, DateTime, Date, Time, GYearMonth, GYear, GMonthDay, GMonth, GDay, Base64Binary, HexBinary,  AnyURI, String, NormalizedString
    return "string"

def get_dict_data_type_from_IEC6360(datatype: model.DataTypeIEC61360):
    """Map DataTypeIEC61360 to "bool", "numeric" or "string"."""
    if datatype == model.DataTypeIEC61360.BOOLEAN:
        return "bool"
    if datatype in [
            model.DataTypeIEC61360.INTEGER_MEASURE,
            model.DataTypeIEC61360.INTEGER_COUNT,
            model.DataTypeIEC61360.INTEGER_CURRENCY,
            model.DataTypeIEC61360.REAL_MEASURE,
            model.DataTypeIEC61360.REAL_COUNT,
            model.DataTypeIEC61360.REAL_CURRENCY,
            model.DataTypeIEC61360.RATIONAL,
            model.DataTypeIEC61360.RATIONAL_MEASURE,
            ]:
        return "numeric"
    return "string"
