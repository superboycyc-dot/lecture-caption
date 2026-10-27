"""Submit a signed build using a Keychain profile, staple and verify Gatekeeper.

No passwords, private keys or certificates are read by this script.
"""

import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def signed_app(app):
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    metadata = subprocess.run(
        ["codesign", "-dv", "--verbose=4", str(app)], capture_output=True, text=True, check=True
    ).stderr
    if (
        "Authority=Developer ID Application:" not in metadata
        or "runtime" not in metadata
        or "Timestamp=" not in metadata
    ):
        raise ValueError("Developer ID Application signing, Hardened Runtime and secure timestamp are required.")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, help="Existing notarytool Keychain profile name, not a password")
    parser.add_argument("--submission-id", help="Resume waiting for an existing submission without uploading again")
    args = parser.parse_args()
    app = ROOT / "dist/Lecture Caption.app"
    signed_app(app)
    build = ROOT / "build/notarization"
    build.mkdir(parents=True, exist_ok=True)
    submission_id = args.submission_id
    if not submission_id:
        archive = build / "LectureCaption-notarization.zip"
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app), str(archive)], check=True)
        response = subprocess.run(
            [
                "xcrun",
                "notarytool",
                "submit",
                str(archive),
                "--keychain-profile",
                args.profile,
                "--output-format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        submission = json.loads(response.stdout)
        (build / "submission.json").write_text(json.dumps(submission, indent=2) + "\n")
        submission_id = submission["id"]
        print("Uploaded; submission ID saved in build/notarization/submission.json", flush=True)
    response = subprocess.run(
        [
            "xcrun",
            "notarytool",
            "wait",
            submission_id,
            "--keychain-profile",
            args.profile,
            "--timeout",
            "30m",
            "--output-format",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    try:
        result = json.loads(response.stdout)
    except ValueError:
        raise SystemExit("No final status received. Resume with --submission-id; do not upload again.") from None
    (build / "status.json").write_text(json.dumps(result, indent=2) + "\n")
    if result.get("status") != "Accepted":
        raise SystemExit(
            "Apple did not accept this submission; inspect build/notarization/submission.json before publishing."
        )
    subprocess.run(["xcrun", "stapler", "staple", str(app)], check=True)
    subprocess.run(["xcrun", "stapler", "validate", str(app)], check=True)
    subprocess.run(["spctl", "--assess", "--type", "execute", "--verbose=4", str(app)], check=True)
    print("Apple accepted the submission; ticket stapled and Gatekeeper assessment passed. Package only now.")


if __name__ == "__main__":
    main()
