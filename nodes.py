import os
import sys
import torch
import folder_paths
import numpy as np
import soundfile as sf
import tempfile
import random

# Add local directory to sys.path so we can import heartlib directly from within the plugin
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from .heartlib import HeartMuLaGenPipeline
except ImportError:
    # Fallback or try direct import if in path
    try:
        from heartlib import HeartMuLaGenPipeline
    except ImportError as e:
        print(f"Failed to import heartlib: {e}")
        HeartMuLaGenPipeline = None

class HeartMuLaLoader:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "mula_model": (folder_paths.get_filename_list("checkpoints"), ),
                "codec_model": (folder_paths.get_filename_list("checkpoints"), ),
                "version": (["3B-merged", "3B-20260123"], {"default": "3B-20260123"}),
                "mula_device": (["cuda", "cpu"], {"default": "cuda"}),
                "codec_device": (["cuda", "cpu"], {"default": "cuda"}),
                "mula_dtype": (["bfloat16", "float16", "float32"], {"default": "bfloat16"}),
                "codec_dtype": (["float32", "float16"], {"default": "float32"}),
                "cpu_offload": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("HEARTMULA_PIPE",)
    RETURN_NAMES = ("pipe",)
    FUNCTION = "load_model"
    CATEGORY = "HeartMuLa"

    def load_model(self, mula_model, codec_model, version, mula_device, codec_device, mula_dtype, codec_dtype, cpu_offload):
        if HeartMuLaGenPipeline is None:
            raise ImportError("heartlib not found. Please ensure heartlib is installed or in the correct path.")

        mula_path = folder_paths.get_full_path("checkpoints", mula_model)
        codec_path = folder_paths.get_full_path("checkpoints", codec_model)
        
        # Determine explicit codec path if available in standard locations
        # We check:
        # 1. Next to the checkpoint (handled by pipeline logic usually, but we can be explicit)
        # 2. ComfyUI/models/heartcodec (custom)
        # 3. ComfyUI/models/checkpoints/HeartCodec-oss (fallback)
        
        explicit_codec_path = codec_path
        
        # Check standard ComfyUI model paths if not found next to checkpoint
        # But we don't know if it's next to checkpoint yet easily without checking.
        # Let's try to find a separate codec path to pass to the pipeline.
        
        # Define candidate paths for Codec
        candidates = []
        
        # 1. ComfyUI/models/heartcodec
        models_dir = folder_paths.models_dir
        heartcodec_global = os.path.join(models_dir, "heartcodec")
        candidates.append(heartcodec_global)
        candidates.append(os.path.join(heartcodec_global, "HeartCodec-oss"))
        
        # 2. ComfyUI/models/checkpoints/HeartCodec-oss
        checkpoints_dir = os.path.join(models_dir, "checkpoints")
        candidates.append(os.path.join(checkpoints_dir, "HeartCodec-oss"))
        
        for p in candidates:
            if os.path.exists(p) and (os.path.exists(os.path.join(p, "model.safetensors")) or os.path.exists(os.path.join(p, "config.json"))):
                 # explicit_codec_path = p
                 # print(f"Found HeartCodec at global path: {explicit_codec_path}")
                 break
        
        # Pass the full checkpoint path directly to the pipeline.
        # The pipeline has been updated to handle file paths (using the file as the model
        # and looking for auxiliary files in the same directory).
        load_path = mula_path
        
        # Map dtype strings to torch dtypes
        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32
        }

        print(f"Loading HeartMuLa model from {mula_path}...")
        print(f"Loading HeartCodec model from {codec_path}...")
        
        # Determine lazy_load based on cpu_offload
        # If cpu_offload is True, we want to load to CPU first (lazy_load=False in pipeline logic, but handled by cpu_offload flag)
        # Actually in our modified pipeline:
        # if cpu_offload: lazy_load = False (overridden)
        # So passing lazy_load=False is fine.
        
        pipe = HeartMuLaGenPipeline.from_pretrained(
            load_path,
            device={
                "mula": torch.device(mula_device),
                "codec": torch.device(codec_device),
            },
            dtype={
                "mula": dtype_map[mula_dtype],
                "codec": dtype_map[codec_dtype],
            },
            version=version,
            lazy_load=False, # We let cpu_offload handle it or load immediately
            cpu_offload=cpu_offload,
            explicit_codec_path=explicit_codec_path,
        )
        
        return (pipe,)

class HeartMuLaGenerator:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "pipe": ("HEARTMULA_PIPE",),
                "vocal_gender": ("STRING", {"default": "Female"}),
                "style_preset": ("STRING", {"default": "None"}),
                "instrument_preset": ("STRING", {"default": "None"}),
                "lyrics": ("STRING", {"multiline": True, "default": "Enter lyrics here"}),
                "tags": ("STRING", {"multiline": True, "default": "emotional, high quality"}),
                "max_audio_length_ms": ("INT", {"default": 10000, "min": 1000, "max": 300000, "step": 1000}),
                "topk": ("INT", {"default": 50, "min": 1, "max": 1000}),
                "temperature": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 2.0, "step": 0.1}),
                "cfg_scale": ("FLOAT", {"default": 1.5, "min": 0.0, "max": 10.0, "step": 0.1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            }
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "generate"
    CATEGORY = "HeartMuLa"

    def generate(self, pipe, lyrics, tags, max_audio_length_ms, topk, temperature, cfg_scale, seed, vocal_gender, style_preset, instrument_preset):
        # Set seed for reproducibility
        # numpy seed must be between 0 and 2**32 - 1
        # ComfyUI can pass larger seeds (up to 2**64 - 1)
        np_seed = seed % (2**32)
        
        torch.manual_seed(seed)
        random.seed(seed)
        np.random.seed(np_seed)
        
        # Construct tags from presets
        gender_map = {
            "Male": "male vocal",
            "Female": "female vocal",
            "Chorus": "chorus",
            "男": "male vocal",
            "女": "female vocal",
            "合唱": "chorus"
        }
        
        preset_tags = []
        if style_preset and style_preset != "None":
            # Support comma-separated styles
            styles = [s.strip() for s in style_preset.split(",") if s.strip() and s.strip() != "None"]
            preset_tags.extend(styles)
            
        preset_tags.append(gender_map.get(vocal_gender, "female vocal"))
        
        if instrument_preset and instrument_preset != "None":
            # Support comma-separated instruments
            instruments = [i.strip() for i in instrument_preset.split(",") if i.strip() and i.strip() != "None"]
            preset_tags.extend(instruments)
            
        # Combine with manual tags
        final_tags_list = preset_tags
        if tags and tags.strip():
            final_tags_list.append(tags)
            
        final_tags = ", ".join(final_tags_list)
        
        print(f"Generating music with lyrics: {lyrics[:20]}... tags: {final_tags}")
        
        # Setup progress bar
        from comfy.utils import ProgressBar
        total_steps = max_audio_length_ms // 80 # Approx steps based on HeartMuLa logic
        pbar = ProgressBar(total_steps)
        
        def progress_callback(step, total):
            pbar.update(1)

        # Run inference
        # The pipeline __call__ method returns a tensor of shape (C, L)
        # We need to capture it.
        # However, the pipeline currently returns None and saves to file inside postprocess.
        # We need to modify or subclass the pipeline, or capture the output.
        # Looking at music_generation.py, postprocess calls sf.write.
        # It doesn't return the audio data.
        # Wait, the __call__ method returns: return self.postprocess(model_outputs, **postprocess_kwargs)
        # And postprocess returns: sf.write(...) which returns nothing?
        # Actually sf.write returns None.
        
        # We need to access the audio tensor before it's saved.
        # We can monkey-patch or use a modified version of the pipeline.
        # Or, since we have the pipe object, we can look at how it works.
        # pipe.postprocess does the detokenization.
        
        # Let's see if we can intercept the audio.
        # In `_forward`, it returns model_outputs.
        # In `postprocess`, it converts to wav.
        
        # Let's create a temporary file to save to, then read it back.
        # This is the easiest way without modifying heartlib further (though we could).
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            pipe(
                {
                    "lyrics": lyrics,
                    "tags": final_tags,
                },
                max_audio_length_ms=max_audio_length_ms,
                save_path=tmp_path,
                topk=topk,
                temperature=temperature,
                cfg_scale=cfg_scale,
                callback=progress_callback,
            )
            
            # Read back with soundfile
            data, samplerate = sf.read(tmp_path)
            # data is (L, C) or (L,) usually from soundfile read?
            # sf.read returns (frames, channels).
            # ComfyUI expects (batch, channels, samples) ?? Or (batch, samples, channels)?
            # Standard AUDIO type in ComfyUI (e.g. LoadAudio) produces:
            # {"waveform": tensor(batch, channels, samples), "sample_rate": int}
            
            # data shape from sf.read:
            # if mono: (L,)
            # if stereo: (L, 2)
            
            if len(data.shape) == 1:
                # Mono -> (1, L)
                waveform = torch.from_numpy(data).unsqueeze(0)
            else:
                # Stereo (L, C) -> (C, L)
                waveform = torch.from_numpy(data.T)
            
            # Add batch dimension -> (1, C, L)
            waveform = waveform.unsqueeze(0)
            
            result = {
                "waveform": waveform,
                "sample_rate": samplerate
            }
            
            return (result,)
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

class HeartMuLaPreview:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "audio": ("AUDIO",),
            },
            "optional": {
                "filename_prefix": ("STRING", {"default": "HeartMuLa/audio"}),
            }
        }

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "save_audio"
    CATEGORY = "HeartMuLa"

    def save_audio(self, audio, filename_prefix="HeartMuLa/audio"):
        # This is similar to ComfyUI's standard SaveAudio node
        # audio dict contains "waveform" and "sample_rate"
        
        waveform = audio["waveform"] # (batch, channels, samples)
        sample_rate = audio["sample_rate"]
        
        # We'll save the first item in batch
        # Save to output directory
        output_dir = folder_paths.get_output_directory()
        full_output_dir = os.path.join(output_dir, os.path.dirname(filename_prefix))
        os.makedirs(full_output_dir, exist_ok=True)
        
        filename = os.path.basename(filename_prefix)
        file = f"{filename}_{random.randint(0, 100000)}.wav"
        path = os.path.join(full_output_dir, file)
        
        # waveform is (1, C, L)
        # squeeze batch
        audio_data = waveform.squeeze(0) # (C, L)
        
        # Convert to (L, C) for soundfile
        audio_numpy = audio_data.cpu().numpy().T
        
        sf.write(path, audio_numpy, sample_rate)
        
        return {"ui": {"audio": [{"filename": file, "subfolder": os.path.dirname(filename_prefix), "type": "output"}]}}

