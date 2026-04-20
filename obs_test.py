from obsws_python import ReqClient
import time

client = ReqClient(
    host="localhost",
    port=4455,
    password="your_password"
)

# Start recording
client.start_record()
print("Recording started")

time.sleep(5)

# Stop recording — THIS returns the file path
response = client.stop_record()

video_path = response.output_path

print("Recording saved to:")
print(video_path)