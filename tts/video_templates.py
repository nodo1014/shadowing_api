#!/usr/bin/env python3
"""비디오 템플릿 정의"""

class VideoTemplate:
    """비디오 템플릿 기본 클래스"""
    def __init__(self):
        self.sequences = []
        
    def get_sequences(self, data, audio_files, durations):
        """템플릿에 따른 시퀀스 반환"""
        raise NotImplementedError


class WordTemplate(VideoTemplate):
    """단어 학습 템플릿"""
    def get_sequences(self, data, audio_files, durations):
        sequences = []
        
        # 1. 한글 뜻 먼저
        sequences.append({
            'type': 'korean_meaning',
            'audio': audio_files['korean'],
            'duration': durations['korean'],
            'subtitle_data': {
                'category': data.get('category', ''),
                'number': data.get('number', ''),
                'korean': data['korean']
            }
        })
        
        # 2. 영어 단어 (3회 반복)
        for i in range(3):
            sequences.append({
                'type': f'english_repeat_{i+1}',
                'audio': audio_files['english'],
                'duration': durations['english'],
                'subtitle_data': {
                    'category': data.get('category', ''),
                    'number': data.get('number', ''),
                    'english': data['english'],
                    'pronunciation': data.get('pronunciation', ''),
                    'korean': data['korean']
                }
            })
            
            # 반복 사이 간격
            if i < 2:
                sequences.append({
                    'type': 'gap',
                    'audio': None,
                    'duration': 2.0,
                    'subtitle_data': {}
                })
        
        return sequences


class BasicSentenceTemplate(VideoTemplate):
    """초급 문장 템플릿"""
    def get_sequences(self, data, audio_files, durations):
        sequences = []
        
        # 1. 한글 먼저
        sequences.append({
            'type': 'korean_first',
            'audio': audio_files['korean'],
            'duration': durations['korean'],
            'subtitle_data': {
                'korean': data['korean']
            }
        })
        
        # 간격
        sequences.append({
            'type': 'gap',
            'audio': None,
            'duration': 1.0,
            'subtitle_data': {}
        })
        
        # 2. 영어 3회 반복
        for i in range(3):
            sequences.append({
                'type': f'english_repeat_{i+1}',
                'audio': audio_files['english'],
                'duration': durations['english'],
                'subtitle_data': {
                    'english': data['english'],
                    'korean': data['korean']
                }
            })
            
            if i < 2:
                sequences.append({
                    'type': 'gap',
                    'audio': None,
                    'duration': 2.0,
                    'subtitle_data': {}
                })
        
        return sequences


class AdvancedSentenceTemplate(VideoTemplate):
    """고급 문장 템플릿 (5단계)"""
    def get_sequences(self, data, audio_files, durations, blank_text=''):
        sequences = []
        
        # 1. 한글만
        sequences.append({
            'type': 'korean_only',
            'audio': audio_files['korean'],
            'duration': durations['korean'],
            'subtitle_data': {
                'category': data.get('category', ''),
                'korean': data['korean']
            }
        })
        
        sequences.append({'type': 'gap', 'audio': None, 'duration': 0.5, 'subtitle_data': {}})
        
        # 2. 무자막 영어
        sequences.append({
            'type': 'english_nosub',
            'audio': audio_files['english'],
            'duration': durations['english'],
            'subtitle_data': {}  # 무자막
        })
        
        sequences.append({'type': 'gap', 'audio': None, 'duration': 0.5, 'subtitle_data': {}})
        
        # 3. 빈칸 채우기 (빈칸이 있는 경우만)
        if blank_text and blank_text != data['english']:
            sequences.append({
                'type': 'english_blank',
                'audio': audio_files['english'],
                'duration': durations['english'],
                'subtitle_data': {
                    'category': data.get('category', ''),
                    'blank_text': blank_text,
                    'note': data.get('note', '')
                }
            })
            
            sequences.append({'type': 'gap', 'audio': None, 'duration': 0.5, 'subtitle_data': {}})
        
        # 4. 완전한 문장
        sequences.append({
            'type': 'english_full',
            'audio': audio_files['english'],
            'duration': durations['english'],
            'subtitle_data': {
                'category': data.get('category', ''),
                'english': data['english'],
                'korean': data['korean'],
                'note': data.get('note', '')
            }
        })
        
        sequences.append({'type': 'gap', 'audio': None, 'duration': 0.5, 'subtitle_data': {}})
        
        # 5. 반복 (무자막)
        sequences.append({
            'type': 'english_final',
            'audio': audio_files['english'],
            'duration': durations['english'],
            'subtitle_data': {}  # 무자막
        })
        
        return sequences


class TemplateFactory:
    """템플릿 팩토리"""
    @staticmethod
    def get_template(template_type):
        templates = {
            'word': WordTemplate(),
            'basic_sentence': BasicSentenceTemplate(),
            'advanced_sentence': AdvancedSentenceTemplate()
        }
        
        template = templates.get(template_type)
        if not template:
            raise ValueError(f"Unknown template type: {template_type}")
        
        return template