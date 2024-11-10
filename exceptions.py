class GetQuoteError(Exception):
    def __init__(self, message):
        super().__init__(f"Error from quote API: {message}")

class BuildTxError(Exception):
    def __init__(self, message):
        super().__init__(f"Error building tx API: {message}")

class NativeTokenNotFound(Exception):
    def __init__(self, message):
        super().__init__(f"Can`t find native token in chain id : {message}")