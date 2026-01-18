# Description: A yt-dlp post-processor plugin to move downloaded videos to a subdirectory based on the channel name.
from __future__ import annotations

import json
import os

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

from enum import Enum
from typing import TYPE_CHECKING, Callable, Tuple

from yt_dlp.postprocessor.common import PostProcessor  # type: ignore
from yt_dlp.utils import PostProcessingError, traverse_obj  # type: ignore

if TYPE_CHECKING:
    import yt_dlp.YoutubeDL as YTDL  # type: ignore

# NOTE: Currently only supports "channel" field
MAPPING_FIELD_PATTERN = r"%\((mapped_\w+)\)s"
MAPPING_CONFIG_TEMPLATE = {
    "uncategorized": {
        "field": {
            "channel": {
                "MIT OpenCourseWare": "OCW - MIT",
                "<CHANNEL NAME>": "<NEW CHANNEL NAME>",
            },
            "<FIELD NAME>": {},
        },
    },
    "<CATEGORY>": {
        "home": "<TARGET LOCATION>",
        "temp": "<TEMP LOCATION>",
        "field": {
            "<FIELD NAME>": {
                "<ORIGINAL FIELD VALUE>": "<NEW FIELD VALUE>",
            },
        },
    },
}


class ConfigTypeEnum(Enum):
    JSON = "JSON"
    YAML = "YAML"


class ChannelMappingPP(PostProcessor):
    """
    Maps (YouTube) channel names to desired channel names

    Use this post-processor before the download process, either in the "pre_process", "after_filter", or "video" position.

    Attributes:
        _kwargs (dict): Additional keyword arguments for this post-processor.
        _mapping (dict): Dictionary containing the channel name mappings.
        _downloader (yt_dlp.YoutubeDL): The downloader instance to be used by the post-processor.

    Methods:
        __init__(downloader=None, **kwargs):
            Initializes the ChannelMappingPP instance and loads the mapping file.
        _save_file(data: dict, file_path: str, file_type: ConfigTypeEnum):
            Saves a dictionary as a file.
        _load_file(file_path: str, file_type: ConfigTypeEnum) -> dict:
            Loads a file as a dictionary.
        write_mapping_template(config_path: str):
            Writes a template mapping file if it does not exist.
        check_config_type(config_path: str) -> ConfigTypeEnum:
            Checks the file type of the configuration file.
        load_mapping(config_path: str) -> dict:
            Loads the mapping file. If the file does not exist, creates a template mapping file.
        is_mapping_used():
            Checks if the variable in the mapping template is used in the mapping file.
        mapping_before_download(information: dict) -> Tuple[list, dict]:
            Maps the channel name to a desired channel name before download and updates the information dictionary.
        mapping_after_download(information: dict) -> Tuple[list, dict]:
            Not implemented. Raises NotImplementedError.
        main_processing(information: dict) -> Tuple[list, dict]:
            Main processing function for the post-processor. Decides which method to call based on the `filepath` presence.
        check_pp_position():
            Checks the position of the post-processor in the list of postprocessors and validates its execution position.
        run(information: dict) -> Tuple[list, dict]:
            Executes the post-processor, checks its position, and performs the main processing.
    """

    # _WORKING = True
    # Valid URL pattern for youtube video, live stream, shorts, and shortened URL.
    # _VALID_URL = r"https?:\/\/(?:www\.)?youtu(?:be\.com\/(?:watch\?v=|live\/|shorts\/)|.be\/)[\w-]+"
    _downloader: YTDL = None

    def __init__(self, downloader=None, **kwargs):
        """
        Initialize the postprocessor with the given downloader and additional keyword arguments.

        Args:
            downloader (Optional[object]): The downloader instance to be used by the postprocessor.
            **kwargs: Additional keyword arguments.

        Attributes:
            _kwargs (dict): Dictionary of additional keyword arguments.
            _mapping (dict): Dictionary containing the loaded mapping data.
        """
        super().__init__(downloader)
        self._kwargs: dict = kwargs

        # Load the mapping file
        _mapping_path: str = self._kwargs.get("config", "")
        _mapping_path = self._normalize_path(_mapping_path)
        self._mapping: dict = self.load_mapping(_mapping_path)
        self.mapped_fields: list = []

    def _normalize_path(self, path: str) -> str:
        """
        Normalize a file path to handle various path formats.

        Handles:
            - Relative paths (e.g., "./config.json", "config.json")
            - Home directory paths (e.g., "~/config.json")
            - Absolute paths (e.g., "/etc/config.json", "C:\\config.json")

        Args:
            path (str): The path to normalize.

        Returns:
            str: The normalized absolute path.
        """
        if not path:
            return path

        # Expand user home directory (e.g., ~/path -> /home/user/path)
        path = os.path.expanduser(path)

        # Expand environment variables (e.g., $HOME/path or %USERPROFILE%/path)
        path = os.path.expandvars(path)

        # Convert to absolute path (handles relative paths)
        path = os.path.abspath(path)

        return path

    def _save_file(self, data: dict, file_path: str, file_type: ConfigTypeEnum):
        """
        Save a dictionary as a file.

        Args:
            data (dict): The dictionary to be saved.
            file_path (str): The path to the file.
            file_type (ConfigTypeEnum): The file type of the file.
        """
        save_func: Callable = None
        if file_type == ConfigTypeEnum.JSON:
            save_func = json.dump
        elif file_type == ConfigTypeEnum.YAML:
            save_func = yaml.dump
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        with open(file_path, "w", encoding="utf-8") as f:
            save_func(data, f, indent=4)

    def _load_file(self, file_path: str, file_type: ConfigTypeEnum) -> dict:
        """
        Load a file as a dictionary.

        Args:
            file_path (str): The path to the file.
            file_type (ConfigTypeEnum): The file type of the file.

        Returns:
            dict: The loaded file as a dictionary.
        """
        load_func: Callable = None
        if file_type == ConfigTypeEnum.JSON:
            load_func = json.load
        elif file_type == ConfigTypeEnum.YAML:
            load_func = yaml.safe_load
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        with open(file_path, "r", encoding="utf-8") as f:
            return load_func(f)

    def write_mapping_template(self, config_path: str):
        """
        Write a template mapping file.

        Raises:
            IOError: If there is an error writing the mapping file.
        """
        # Ensure the directory exists
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        # Write the template mapping file
        try:
            self._save_file(MAPPING_CONFIG_TEMPLATE, config_path, self.check_config_type(config_path))
            self.report_warning(f"Mapping file not found. Created a template mapping file at: {config_path}")
        except Exception as exc:
            raise IOError(f"Can't write mapping file: {config_path}") from exc

    def check_config_type(self, config_path: str) -> ConfigTypeEnum:
        """
        Check the file type of the configuration file.

        Args:
            config_path (str): The path to the configuration file.

        Returns:
            ConfigTypeEnum: The file type of the configuration file.
        """
        ext: str = os.path.splitext(config_path)[1].lower()
        ext_format: ConfigTypeEnum = None
        if ext in [".json"]:
            ext_format = ConfigTypeEnum.JSON
        elif ext in [".yaml", ".yml"] and yaml is not None:
            ext_format = ConfigTypeEnum.YAML
        else:
            raise ValueError(f"Unsupported file type: {ext}")
        return ext_format

    def load_mapping(self, config_path: str) -> dict:
        """
        Load the mapping file.
        If the file does not exist, create a template mapping file and load it.

        Returns:
            dict: A dictionary containing the mappings loaded from the file.
        """
        # Create a template mapping file if the file does not exist
        if not os.path.exists(config_path):
            self.write_mapping_template(config_path)

        # Load the mapping file
        mapping: dict = self._load_file(config_path, self.check_config_type(config_path))
        return mapping

    def is_mapping_used(self) -> list:
        """
        Check if the variable in the mapping template is used in the mapping file.

        Returns:
            list: A list of the mapped fields found in the file template.
        """
        # The template should be like "%(mapped_channel)s"
        file_template = traverse_obj(self._downloader.params, ["outtmpl", "default"], default="")
        return "%(mapped_channel)s" in file_template

    def find_field(self, original_channel: str, category_dict: dict) -> Tuple[str, str]:
        """
        Find the mapped field name based on the original channel name.

        Args:
            original_channel (str): The original channel name.
            category_dict (str): The category name.

        Returns:
            Tuple[str, str]: The matched field name and the new field name.
        """
        for field, field_data in category_dict.get("field", {}).items():
            new_field_name: str = field_data.get(original_channel, "")
            if new_field_name:
                return field, new_field_name
        return "", ""

    def find_category(self, original_channel: str, default: str = "") -> Tuple[dict, str, str]:
        """
        Find the mapped channel name based on the original channel name.

        Args:
            original_channel (str): The original channel name.

        Returns:
            Tuple[dict, str, str]: The matched category data, the matched field name, and the new field name.
        """
        for category, category_data in self._mapping.items():
            # Find the mapped field name
            field, new_field_name = self.find_field(original_channel, category_data)
            if new_field_name:
                return category_data, field, new_field_name
        return {}, "", default

    def change_path(self, category: dict, dir_type: str):
        """
        Change the directory of the downloaded file based on the category and directory type.

        Args:
            category (dict): The category data containing the directory location.
            dir_type (str): The type of directory to change ("home" or "temp").
        """
        new_location: str = category.get(dir_type, "")
        if not new_location:
            return

        new_location: str = os.path.realpath(new_location)
        os.makedirs(new_location, exist_ok=True)
        self._downloader.params["paths"][dir_type] = new_location

    def mapping_before_download(self, information: dict) -> Tuple[list, dict]:
        """
        Mapping the channel name into a desired channel name.
        New field `mapped_channel` will be added to the information dictionary,
        which contains the mapped channel name. If the original channel name is
        not found in the mapping, it will remain unchanged.

        Args:
            information (dict):
                A dictionary containing video information, including the original
                channel name under the key "channel".
        Returns:
            Tuple[list, dict]:
                A tuple containing an empty list and the updated information dictionary
                with the new `mapped_channel` field.
        """
        # TODO: Different approach required to support any other fields efficiently
        original_channel: str = information.get("channel", "")

        # Find the mapping
        category, field, new_channel_name = self.find_category(original_channel, default=original_channel)

        # Change the target directory
        self.change_path(category, "home")  # Target directory
        self.change_path(category, "temp")  # Temporary download directory
        self.to_screen(
            f"Original channel: \033[33m{original_channel}\033[39m -> New channel: \033[32m{new_channel_name}\033[39m"
        )
        mapped_field_name: str = f"mapped_{field or 'channel'}"

        # Add the mapped channel name to the information dictionary
        information.update({mapped_field_name: new_channel_name})
        self.mapped_fields.append(mapped_field_name)
        return [], information

    def mapping_after_download(self, information: dict) -> Tuple[list, dict]:
        """
        This method is intended to perform mapping operations after a download is completed.

        Args:
            information (dict): A dictionary containing information about the downloaded content.

        Returns:
            Tuple[list, dict]: A tuple containing a list and a dictionary. The exact structure and content
                               of these return values are not defined as the method is not implemented yet.

        Raises:
            NotImplementedError
        """
        # NOTE: Not implemented yet as it is not necessary for the current use case AND might be too complicated
        # NOTE: Need to tidy up yt_dlp's `information` dict first :<
        _this_class_name = self.__class__.__name__[:-2]
        raise NotImplementedError(
            f'Not implemented yet. Consider set {_this_class_name} at "pre_process" instead '
            '("pre_process", "after_filter" and "video" are tested working) e.g. '
            f'--use-postprocessor "{_this_class_name}:when=pre_process"'
        )

    def main_processing(self, information: dict) -> Tuple[list, dict]:
        """
        Main processing function for the post-processor.
        Decides which method to call based on the `filepath` key in the
        `information` dictionary.

        Args:
            information (dict): A dictionary containing information about the download process.

        Returns:
            Tuple[list, dict]: The result of the processing, which can be a list and a dictionary.

        Raises:
            PostProcessingError: If the after download mapping is not implemented.
        """
        # Before download
        if not information.get("filepath", False):
            return self.mapping_before_download(information)

        # After download
        # REVIEW: Should we implement the after download mapping?
        _this_class_name = self.__class__.__name__[:-2]
        try:
            return self.mapping_after_download(information)
        except NotImplementedError as exc:
            raise PostProcessingError(
                f'Not implemented yet. Consider set {_this_class_name} at "pre_process" instead '
                '("after_filter" and "video" are tested working) e.g. '
                f'--use-postprocessor "{_this_class_name}:when=pre_process"'
            ) from exc

    def check_pp_position(self):
        """
        Check the position of the post-processor in the list of postprocessors and validate its execution position.

        This method retrieves the list of postprocessors from the downloader's parameters, locates the current
        post-processor in that list, and checks its execution position. The execution position must be one of
        the valid values: 'pre_process', 'after_filter', or 'video'. If the execution position is invalid, a
        PostProcessingError is raised.

        Raises:
            PostProcessingError: If the execution position is not one of the valid values.
        """
        # Locate the position of this post-processor in the list
        pp_list: list = self._downloader.params.get("postprocessors", [])
        pp_position = -1
        for i, pp in enumerate(pp_list):
            if pp.get("key") == self.__class__.__name__[:-2]:
                pp_position = i
                break

        # Check the execution position of this post-processor
        pp_exec_info: dict = pp_list[pp_position] if pp_position >= 0 else {}
        pp_exec_position: str = pp_exec_info.get("when", "post_process")  # Default: post_process

        # Validate the execution position
        # NOTE: Processing at any other positions are more complicated and not necessary for the current use case
        supported_pp_positions: list = ["pre_process", "after_filter", "video"]
        if pp_exec_position not in supported_pp_positions:
            raise ValueError(
                f'Invalid "when" value "{pp_exec_position}" for post-processor "{self.__class__.__name__[:-2]}"'
                f" (should be: {', '.join(supported_pp_positions)})"
            )

    def run(self, information: dict) -> Tuple[list, dict]:
        """
        Executes the post-processing steps for the given information.

        Args:
            information (dict): The information dictionary to be processed.

        Returns:
            tuple: A tuple containing a list of deletable items and the processed information dictionary.
        """
        deletable: list = []

        # Skip if the mapping is not used
        if not self.is_mapping_used():
            return deletable, information

        # Attempt to process the information
        try:
            self.check_pp_position()
            deletable, information = self.main_processing(information)
        except Exception:
            pass
        finally:  # Clean up afterwards
            self._downloader.add_post_processor(_post_cleanup(self.mapped_fields), when="after_video")

        return deletable, information


# Post-processor to remove every added field from ChannelMappingPP in the information dictionary
def _post_cleanup(keys: list) -> PostProcessor:
    """
    Remove every added field from ChannelMappingPP in the information dictionary.

    Args:
        keys (list): A list of keys to be removed from the information dictionary.

    Returns:
        PostProcessor: A post-processor instance to remove the added fields from the information dictionary.
    """

    class PostCleanupPP(PostProcessor):
        """
        Clean up the information dictionary by removing added fields from ChannelMappingPP.
        """

        def run(self, information: dict) -> Tuple[list, dict]:
            """
            Remove the previously added fields by ChannelMappingPP from the information dictionary.

            Args:
                information (dict): The dictionary containing information to be processed.

            Returns:
                tuple: A tuple containing an empty list and the processed information dictionary.
            """
            for key in keys:
                information.pop(key, None)
            return [], information

    return PostCleanupPP()
