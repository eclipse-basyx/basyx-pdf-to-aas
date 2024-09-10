import logging

from basyx.aas import model

from ..extractor import Property

logger = logging.getLogger(__name__)

def cast_property(value, definition) -> model.ValueDataType:
    if value is None:
        return None
    if definition is not None:
        match definition.type:
            case 'bool': return model.datatypes.Boolean(value)
            case 'numeric' | 'range':
            # Range is catched earlier and should not be reached
                try:
                    casted = float(value)
                except (ValueError, TypeError):
                    return model.datatypes.String(value)
                if casted.is_integer():
                    casted = int(casted)
                    return model.datatypes.Integer(casted)
                return model.datatypes.Float(casted)
            case 'string': return model.datatypes.String(value)
    
    if isinstance(value, bool):
        return model.datatypes.Boolean(value)
    if isinstance(value, int):
        return model.datatypes.Integer(value)
    if isinstance(value, float):
        if value.is_integer():
            return model.datatypes.Integer(value)
        return model.datatypes.Float(value)
    return model.datatypes.String(value)

def cast_range(property_: Property):
    min, max = property_.parse_numeric_range()
    if isinstance(min, float) or isinstance(max, float):
        return None if min is None else float(min), None if max is None else float(max), model.datatypes.Float
    if isinstance(min, int) or isinstance(max, int):
        return None if min is None else int(min), None if max is None else int(max), model.datatypes.Integer
    else:
        return None, None, model.datatypes.String # XSD has no equivalent to None
