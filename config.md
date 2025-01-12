# LazyAnki Configurations

This documentation outlines the configuration options for the LazyAnki add-on.

### Default Field Names

- **`default_word_field`**: The default `word` field name. The word serves as the question and is displayed as the largest and boldest text on the screen by default.  
- **`default_reading_field`**: The default `reading` field name. The reading appears above the word, smaller by default. It can include phonetic IPA transcriptions, furigana, etc.  
- **`default_meaning_field`**: The default `meaning` field name. The meanings are used as the answer options.  
- **`default_audio_field`**: The default `audio` field name. The audio plays automatically before an answer is chosen.  

### Window Appearance

- **`window_title`**: The title text of the player window.  
- **`window_width_px`**: The width of the player window (in pixels).  
- **`window_height_px`**: The height of the player window (in pixels).  
- **`window_position_x_px`**: The horizontal position of the player window (in pixels). Set this to `-1` for the default automatic position.  
- **`window_position_y_px`**: The vertical position of the player window (in pixels). Set this to `-1` for the default automatic position.  
- **`window_css`**: The CSS styling for the player window.  

### Timer

- **`default_answer_time_sec`**: The amount of time (in seconds) allotted to answer a question.  
- **`default_correct_time_ms`**: The duration (in milliseconds) for displaying the result when the answer is correct.
- **`default_failed_time_ms`**: The duration (in milliseconds) for displaying the correct answer when the answer was skipped, incorrect, or time ran out.

### Text Stylesheets

- **`style_answer_any`**: The text style for answer options, serving as the base style for both correct and incorrect answers.  
- **`style_answer_wrong`**: Additional style attributes for marking incorrect answers.  
- **`style_answer_correct`**: Additional style attributes for marking correct answers.  
- **`style_timer_any`**: The text style for the timer.  
- **`style_timer_green`**: Additional style attributes for displaying the timer in green. 
- **`style_timer_red`**: Additional style attributes for displaying the timer in red. This style is applied for "wrong answer," "timeout," or "don't know" messages.  
- **`style_reading_text`**: The text style for the "reading," displayed above the current word.  
- **`style_word_text`**: The text style for the current word.  

### Other

- **`default_option_count`**: The default number of answer options per question. Must be set between `2` and `9` (default `4`).  

<hr>

**Author**: Pavlo Savchuk.<br>
**GitHub**: [url](https://github.com/zegalur/lazy-anki)