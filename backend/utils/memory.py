import json
import os
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()


class ChatMemory:
    """
    Memory storage for the chat.
    """

    def __init__(self) -> None:
        self.USE_S3 = os.getenv("USE_S3", "false").lower() == "true"
        self.S3_BUCKET = os.getenv("S3_BUCKET", "")
        self.MEMORY_DIR = os.getenv("MEMORY_DIR", "../memory")

        self._s3_client = boto3.client("s3")

    def load_conversation(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Load conversation history from storage

        Args:
            session_id: The ID of the session to load the conversation history for

        Returns:
            A list of dictionaries representing the conversation history
        """

        if self.USE_S3:
            try:
                response = self._s3_client.get_object(
                    Bucket=self.S3_BUCKET,
                    Key=self._get_memory_path(session_id),
                )
                body = response["Body"].read().decode("utf-8")
                result: List[Dict[str, Any]] = json.loads(body)
                return result
            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchKey":
                    return []
                raise
        else:
            file_path = os.path.join(self.MEMORY_DIR, self._get_memory_path(session_id))
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    loaded: List[Dict[str, Any]] = json.load(f)
                    return loaded
            return []

    def save_conversation(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """
        Save conversation history to storage

        Args:
            session_id: The ID of the session to save the conversation history for
            messages: A list of dictionaries representing the conversation history
        """

        if self.USE_S3:
            self._s3_client.put_object(
                Bucket=self.S3_BUCKET,
                Key=self._get_memory_path(session_id),
                Body=json.dumps(messages, indent=2),
                ContentType="application/json",
            )
        else:
            os.makedirs(self.MEMORY_DIR, exist_ok=True)
            file_path = os.path.join(self.MEMORY_DIR, self._get_memory_path(session_id))
            with open(file_path, "w") as f:
                json.dump(messages, f, indent=2)

    def _get_memory_path(self, session_id: str) -> str:
        return f"{session_id}.json"
