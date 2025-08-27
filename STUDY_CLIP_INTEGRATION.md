# Study Clip Integration into New Clipping System

## Overview
The img_tts_generator has been successfully integrated into the template system with dedicated template numbers for API clip requests.

## Template Numbers

### Study Clips (31-39)
- **31**: Study Preview Clip (일반 화면 미리보기)
- **32**: Study Review Clip (일반 화면 복습)
- **33**: Study Shorts Preview Clip (쇼츠 미리보기)
- **34**: Study Shorts Review Clip (쇼츠 복습)
- **35-39**: Reserved for future study clip variations

## API Usage

### Single Clip Request
```json
POST /api/clips/create

{
  "media_path": "/path/to/video.mp4",
  "start_time": 50.0,
  "end_time": 52.5,
  "text_eng": "You will be Hunters.",
  "text_kor": "너희는 헌터가 될 거야.",
  "template_number": 31,  // Study preview
  "individual_clips": false
}
```

### Batch Request with Study Clips
```json
POST /api/clips/batch

{
  "media_path": "/path/to/video.mp4",
  "template_number": 32,  // Study review
  "clips": [
    {
      "start_time": 50.0,
      "end_time": 52.5,
      "text_eng": "You will be Hunters.",
      "text_kor": "너희는 헌터가 될 거야."
    },
    {
      "start_time": 55.0,
      "end_time": 58.0,
      "text_eng": "The world needs heroes.",
      "text_kor": "세상은 영웅이 필요해."
    }
  ]
}
```

## Template Configuration

### Template JSON Structure
```json
{
  "template_study_preview": {
    "name": "Study Clip - Preview",
    "description": "스터디 미리보기 클립 (정지화면 + TTS)",
    "clips": [
      {
        "subtitle_mode": "study_preview",
        "folder_name": "study_preview",
        "count": 1,
        "subtitle_type": null,
        "video_mode": "still_frame_tts",
        "use_img_tts_generator": true
      }
    ],
    "gap_duration": 0
  }
}
```

## Features

### Preview Mode (템플릿 31, 33)
- Normal TTS speed (+0%)
- Title: "스피드 미리보기"
- Used for quick preview of content

### Review Mode (템플릿 32, 34)
- Slower TTS speed (-10%)
- Title: "스피드 복습"
- Used for study and practice

### Shorts vs Regular
- **Regular (31, 32)**: 1920x1080 resolution, no cropping
- **Shorts (33, 34)**: 1080x1920 resolution, 70% width crop

## Implementation Details

### 1. Template Video Encoder Updates
- Added `_encode_study_clip()` method
- Imports `ImgTTSGenerator` for still frame + TTS generation
- Handles async execution within sync context
- Applies appropriate crop filters for shorts

### 2. Clipping API Updates
- Updated template number descriptions
- Added template mapping for study clips
- Template numbers 31-34 mapped to study templates

### 3. Template Patterns
- New templates added to `shadowing_patterns.json`
- Special `video_mode: "still_frame_tts"` triggers img_tts_generator
- `use_img_tts_generator: true` flag for clarity

## Testing

Run the test script:
```bash
python test_study_clip_integration.py
```

This will create test clips for all four study templates.

## Future Enhancements

### Reserved Template Numbers (35-39)
Possible future variations:
- **35**: Study clip with original audio (no TTS)
- **36**: Study clip with bilingual TTS
- **37**: Study clip with vocabulary highlights
- **38**: Study clip with grammar explanations
- **39**: Study clip with pronunciation guide

### Customization Options
The img_tts_generator supports:
- Custom fonts and styling
- Multiple text overlays
- Audio extraction from original video
- Color backgrounds
- Text animations

## Notes
- Study clips are single clips (no concatenation needed)
- TTS voice is always en-US-AriaNeural
- Font styling follows existing template standards
- Crop filters match main clip settings for consistency