import os
from http import HTTPStatus
import botocore.exceptions
from requests import Response


class FailedResponseError(RuntimeError):
    def __init__(
        self,
        response: Response | botocore.exceptions.ClientError,
        additional_information: Optional[str] = None,
    ):
        if isinstance(response, botocore.exceptions.ClientError):
            self.response = response.response
        else:
            self.response = response

        status_code = response.status_code

        blocks = {
            "Status code": status_code,
            "Reason": response.reason,
            "History": response.history,
            "Headers": response.headers,
        }

        text = response.text

        if text:
            tabbed_text = [f"\t{line}" for line in text.splitlines()]

            blocks["Content"] = os.linesep.join(tabbed_text)

        phrase = HTTPStatus(status_code).phrase
        msg = [f"[{phrase}] Request from {response.url} failed:"]

        if additional_information:
            msg.append(f"\n\tAdditional information: {additional_information}\n")

        for block_key, block_contents in blocks.items():
            msg.append(f"{block_key}:\n\n{block_contents}\n")

        super().__init__(os.linesep.join(msg))
