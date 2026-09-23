---
language:
- en
pretty_name: "Ego Mistake Corrections Benchmark - Subsampled"
license: other
task_categories:
- video-text-to-text
tags:
- streaming
- video
- text
- multimodal
- cooking
annotations_creators:
- expert-generated
multilinguality: monolingual
source_datasets:
- original
size_categories:
- 1K<n<10K
configs:
- config_name: default
  data_files:
  - split: test
    path: annotations/annotations.json
dataset_info:
- config_name: default
  features:
  - name: video_id
    dtype: string
  - name: texts
    sequence: string
  - name: text_types
    sequence: string
  - name: text_timestamps
    sequence: float64
  splits:
  - name: test
    num_examples: 7
---

# Ego Mistake Corrections Benchmark (Ego-MC-Bench) - Random Sample

## Release Files

- `annotations/annotations.json`
- `videos/*.MP4`
- `sample_manifest.json`

## Sample Statistics

- Total videos: 7
- Total annotations: 253

Selected videos:
- `GX010021`
- `GX010029`
- `GX010033`
- `GX010037`
- `GX010049`
- `GX010053`
- `GX010063`

Text type counts:
- `Feedback`: 54
- `Instruction`: 85
- `Instruction-Clarification`: 10
- `Success`: 82
- `User-Comment`: 12
- `User-Question`: 10

## Data Format

Each row in `annotations.json` has schema:

```json
{
  "video_id": "GX010021",
  "texts": ["Let's first preheat the oven to 350 degrees Fahrenheit."],
  "text_types": ["Instruction"],
  "text_timestamps": [4.418]
}
```

Video asset convention:

- `videos/<video_id>.MP4`

## Dataset License

This dataset is released for research purposes only.
