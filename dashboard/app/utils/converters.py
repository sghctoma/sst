import uuid

from werkzeug.routing import BaseConverter


class UuidConverter(BaseConverter):

    def to_python(self, value):
        return uuid.UUID(value)

    def to_url(self, value):
        return value.hex
