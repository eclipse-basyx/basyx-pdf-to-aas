class PropertyExtractor:
    def extract(self, input: str) -> str:
        raise NotImplementedError()


class SimplePropertyExtractor:
    def extract(self, input: str) -> str:
        return '{ "property_x":"12", "property_y":42}'
