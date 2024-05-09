class InvalidSymbolsError(Exception):
    def __init__(self, got, expected):
        self.token = got
        self.expected = expected

    def __str__(self):
        return f"Got invalid symbols or tokens: {self.token}, expected: {self.expected}"
