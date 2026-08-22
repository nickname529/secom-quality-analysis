# Raw data

Run `python scripts/download_data.py` from the project root to download the
official UCI SECOM archive and extract the following source files here:

- `secom.data`
- `secom_labels.data`
- `secom.names`

Source: https://archive.ics.uci.edu/dataset/179/secom

The download script checks the archive and extracted files against pinned
SHA-256 values in `scripts/download_data.py`, then records the result in
`source_manifest.json`. A mismatch stops the script. Raw files are not
modified by the analysis.
