# test_args.py
import sys

if len(sys.argv) < 2:
    print("Usage: python test_args.py <file.wav>")
    sys.exit(1)

audio_file = sys.argv[1]
print("Got audio file:", audio_file)
