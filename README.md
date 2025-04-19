# yt_dlp mapping

Organize by maps the (supposedly) channel name into your desired name

e.g. directory of `MIT OpenCourseWare/<...>.mp4` -> `OpenCourse - MIT/<..>.mp4`

## Installing

To install this postprocessor, you may clone this repository into [yt_dlp plugin directory](https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#installing-plugins)

```bash
cd <your desired plugin directory>  # e.g. ~/.yt-dlp/plugins
git clone <url to this repository>
```

and run the following command:

```bash
python -m pip install .
```

Depending on your system, you may need to use `python3` instead of `python`.

## Usage

To use this postprocessor, add the following tag to the command line or inside the `yt-dlp.conf` configuration file:

```bash
--use-postprocessor "ChannelMapping:when=pre_process;config=~/.yt_dlp/mapping.json"
```

where `config` is the path to the config file in JSON / YAML format, `when` is the time to run the postprocessor (more on that on [the original documentation](https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#post-processing-options)).

> [!TIP]
> If you want to use YAML format, please install `pyyaml` package first by running `python -m pip install pyyaml`.

> [!IMPORTANT]
> At the moment, any `when` values other than `pre_process`, `after_filter` or `video` are not guaranteed to work and thus they are disabled. Suggested to use `pre_process`.

Then change the `%(channel)s` parameter in the output template to `%(mapped_channel)s`:

```bash
-o "%(mapped_channel)s/%(title)s.%(ext)s"
```

The config file should contains the channel name as the key and the desired mapping name as the value. The structure should be as follows:

```json
{
    "online_courses": {
        "home": "~/archive/course",
        "temp": "/tmp/yt-dlp",
        "field": {
            "channel": {
                "MIT OpenCourseWare": "OpenCourse - MIT",
                "YaleCourses": "OpenCourse - Yale",
                "<CHANNEL NAME>": "<NEW CHANNEL NAME>"
            }
        }
    },
    "<CATEGORY>": {
        "home": "<TARGET LOCATION>",
        "temp": "<TEMP LOCATION>",
        "field": {
            "channel": {
                "<CHANNEL NAME>": "<NEW CHANNEL NAME>"
            }
        }
    }
}
```

> [!NOTE]
> Only `channel` field is supported at the moment.

> [!IMPORTANT]
> - The mapping is case sensitive and should be exactly the same as the channel name.
> - In case the channel name is not found in the mapping, the original channel name will be used instead.
> - If there are duplicates (multiple mappings for the same channel name), the first mapping found will be used.

## TODO

- [ ] ~~Allow post-processing execution~~ (too complicated)
  - Complicated execution flow
  - Messy information provided by the yt-dlp itself (detailed documentation is needed)
- [ ] E x p a n d  mapping features
  - [ ] Field support e.g. `channel_id` or `playlist_id` ([!] may require different approach)
    - [ ] Regex matching method
    - [ ] Override output template
  - [x] Override output (and temp) directory
- [ ] Another organizing functionalities
  - [x] Categorizing
  - [ ] Playlist mapping

## Contributing

Feel free to contribute to this repository by creating a pull request or issue. Any suggestions or improvements are welcome. Just remember to always follow the common best practices of writing code, including but not limited to writing documentation and maintaining code readability.
