from enum import Enum


class ClaudeModels(Enum):
    SONNET = "claude-3-sonnet-20240229"
    HAIKU = "claude-3-haiku-20240307"
    OPUS = "claude-3-opus-20240229"
    SONNET_3_5 = "claude-3-5-sonnet-20240620"

    @staticmethod
    def model_is_plus(model):
        return model in [ClaudeModels.OPUS.value, ClaudeModels.HAIKU.value, ClaudeModels.SONNET_3_5.value]

    @staticmethod
    def model_is_basic(model):
        return model in [ClaudeModels.SONNET.value]
