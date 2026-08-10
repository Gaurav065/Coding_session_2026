import wave

def crop_wav(input_file, output_file, start_sec, end_sec):
    try:
        with wave.open(input_file, 'rb') as w_in:
            params = w_in.getparams()
            frames_per_sec = params.framerate
            
            # Move to start_sec
            w_in.setpos(int(start_sec * frames_per_sec))
            
            # Read frames up to end_sec
            frames_to_read = int((end_sec - start_sec) * frames_per_sec)
            frames = w_in.readframes(frames_to_read)
            
        with wave.open(output_file, 'wb') as w_out:
            w_out.setparams(params)
            w_out.writeframes(frames)
            
        print(f"Successfully cropped to {output_file}")
    except Exception as e:
        print(f"Error cropping audio: {e}")

if __name__ == "__main__":
    # I am assuming the talking starts around 10 seconds in and grabbing a 10s clip
    crop_wav("Solaire of Astora Dialogues [English subtitles, Timestamps, 1080p HD].wav", "reference.wav", 10.0, 20.0)
