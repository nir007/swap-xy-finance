class GetQuoteError(Exception):
    def __init__(self, message):
        super().__init__(f"Error from quote API: {message}")

class AssembleError(Exception):
    def __init__(self, message):
        super().__init__(f"Error from assemble API: {message}")

class TokenNotFound(Exception):
    def __init__(self, message):
        super().__init__(f"Can`t find token: {message}")