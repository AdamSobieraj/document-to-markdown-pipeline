

### 1. How to run from the CLI

Here are examples of how to run different scenarios:

**Scenario A: Local to Local**
Convert files from a local directory and save them to another local directory.
```bash
python MarkDownConverter.py --source-type local --dir ./my_input_docs --out-dir ./my_output_md
```

**Scenario B: S3 to S3**
Convert files from an S3 bucket and save them to a different S3 bucket.
```bash
python MarkDownConverter.py --source-type s3 --bucket my-input-bucket --prefix documents/ --out-bucket my-output-bucket
```

**Scenario C: S3 to Local**
Download/Convert files from S3 and save the resulting markdown locally.
```bash
python MarkDownConverter.py --source-type s3 --dest-type local --bucket my-company-docs --out-dir ./local_markdown
```

**Scenario D: Run with Debug Logging**
If something goes wrong and you want to see the `logger.debug` messages from your `process_single_file` function, just add `--debug`:
```bash
python MarkDownConverter.py --source-type local --dir ./my_input_docs --debug
```

### Note on Environment Variables
Because your script interacts with AWS S3, ensure you have your AWS credentials configured in your environment before running the CLI, for example:
```bash
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
export AWS_DEFAULT_REGION="us-east-1"
```
*(Or just ensure `aws configure` has been run on your machine).*

mojsuperbucket