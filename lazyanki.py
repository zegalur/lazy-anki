"""
LazyAnki is an Anki add-on designed to streamline the review process for 
language learners. It transforms traditional flashcard reviews into a series of 
multiple-choice questions with minimal time required per question, while 
maintaining meaningful language exposure.
"""

import aqt
from aqt import mw
from aqt.utils import showInfo
from aqt.utils import qconnect
from aqt.qt import *

import random


class LazyAnkiWnd(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Read the config file.
        config = mw.addonManager.getConfig(__name__)

        # Get default field names.
        self.WORD_FIELD = config['default_word_field']
        self.READING_FIELD = config['default_reading_field']
        self.MEANING_FIELD = config['default_meaning_field']
        self.AUDIO_FIELD = config['default_audio_field']

        # Read the style attributes.

        self.setStyleSheet(config['window_css'])

        self.ANSWER_STYLE = config['style_answer_any']
        self.ANSWER_STYLE_WRONG = self.ANSWER_STYLE + config['style_answer_wrong']
        self.ANSWER_STYLE_CORRECT = self.ANSWER_STYLE + config['style_answer_correct']

        self.TIMER_STYLE_NO_COLOR = config['style_timer_any']
        self.TIMER_STYLE_GREEN = self.TIMER_STYLE_NO_COLOR + config['style_timer_green']
        self.TIMER_STYLE_RED = self.TIMER_STYLE_NO_COLOR + config['style_timer_red']

        self.READING_STYLE = config['style_reading_text']
        self.WORD_STYLE = config['style_word_text']

        # Setup the timer
        self.OPTION_COUNT = config['default_option_count']
        self.TIMER_SEC = config['default_answer_time_sec']
        self.RESULT_TIMER_MS = config['default_result_time_ms']
        self.time_left_sec = 0

        self.correct_answer = -1
        self.new_cards = []

        # State machine constants and variables.
        self.STATE_INITIAL = "INITIAL"
        self.STATE_COUNTDOWN = "COUNTDOWN"
        self.STATE_ANSWER = "ANSWER"
        self.STATE_DONE = "DONE"
        self.STATE_NEW = "NEW"
        self.state = self.STATE_INITIAL

        random.seed()

        # Create a QTimer.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer)

        # Setup the window.

        self.setWindowTitle(config['window_title'])
        self.resize(config['window_width_px'], config['window_height_px'])
        px = config['window_position_x_px']
        py = config['window_position_y_px']
        if px >= 0 and py >= 0:
            self.move(px, py)
        wndLayout = QFormLayout()
        self.setLayout(wndLayout)

        # Timer Label
        self.timerLabel = QLabel("PLEASE WAIT...")
        self.timerLabel.setAlignment(aqt.Qt.AlignmentFlag.AlignCenter)
        self.timerLabel.setStyleSheet(self.TIMER_STYLE_NO_COLOR)
        wndLayout.addRow(self.timerLabel)

        self.show()

        # Generate false answers list.
        active_deck_ids = mw.col.decks.active()
        self.false_answers = []
        for deck_id in active_deck_ids:
            deck = mw.col.decks.get(deck_id)
            deck_card_ids = mw.col.find_cards('"deck:%s"'%(deck["name"]))
            for card_id in deck_card_ids:
                note = mw.col.get_card(card_id).note()
                self.false_answers.append(note[self.MEANING_FIELD])
        self.false_answers_set = set(self.false_answers)

        self.timerLabel.setText("---")

        # Reading
        self.readingLabel = QLabel("[Reading]")
        self.readingLabel.setAlignment(aqt.Qt.AlignmentFlag.AlignCenter)
        self.readingLabel.setStyleSheet(self.READING_STYLE)
        wndLayout.addRow(self.readingLabel)

        # Word
        self.wordLabel = QLabel("[Word]")
        self.wordLabel.setAlignment(aqt.Qt.AlignmentFlag.AlignCenter)
        self.wordLabel.setStyleSheet(self.WORD_STYLE)
        wndLayout.addRow(self.wordLabel)

        # Options
        self.options = []
        for i in range(self.OPTION_COUNT):
            optionLabel = QLabel("[Option]")
            optionLabel.setAlignment(aqt.Qt.AlignmentFlag.AlignLeft)
            optionLabel.setStyleSheet(self.ANSWER_STYLE)
            wndLayout.addRow(optionLabel)
            self.options.append(optionLabel)

        self._showNextCard()
    

    def closeEvent(self, event):
        self.timer.stop()
        mw.reset()


    def keyPressEvent(self, event):
        if self.state in [self.STATE_DONE, self.STATE_INITIAL]:
            super().keyPressEvent(event)
            return

        scan_code = event.key()

        if self.state == self.STATE_COUNTDOWN:
            if scan_code >= aqt.Qt.Key.Key_0:
                if scan_code <= self.OPTION_COUNT + aqt.Qt.Key.Key_0:
                    self._selectAnswer(scan_code - aqt.Qt.Key.Key_1)

        if self.state == self.STATE_NEW:
            if scan_code in [aqt.Qt.Key.Key_Enter, aqt.Qt.Key.Key_Return]:
                self._showNextCard()

        super().keyPressEvent(event)
            


    def _showNextCard(self) -> None:
        # Reset the timer.
        self.timer.stop()
        self.time_left_sec = self.TIMER_SEC
        self._updateTimerText()
        
        self.current_card = card = mw.col.sched.getCard()
        if not card:
            self._showDone()
            return

        note = card.note()
        self.wordLabel.setText(note[self.WORD_FIELD])
        self.readingLabel.setText(note[self.READING_FIELD])

        # Play the audio.
        audio_file = note[self.AUDIO_FIELD].removeprefix("[sound:").removesuffix("]")
        aqt.sound.av_player.play_file(audio_file)

        # Get some random false answers.
        false_answers = []
        tmp_copy = self.false_answers_set.copy()
        tmp_copy.remove(note[self.MEANING_FIELD])
        for i in range(self.OPTION_COUNT - 1):
            if len(tmp_copy) == 0:
                break
            new_false_answer = list(tmp_copy)[random.randint(0, len(tmp_copy) - 1)]
            false_answers.append(new_false_answer)
            tmp_copy.remove(new_false_answer)

        # Set the correct answer.
        self.correct_answer = random.randint(0, len(false_answers))
        self.options[self.correct_answer].setText(note[self.MEANING_FIELD])

        # Set the false answers.
        i = 0
        for false_answer in false_answers:
            if i == self.correct_answer:
                i += 1
            self.options[i].setText(false_answer)
            i += 1
        for j in range(self.OPTION_COUNT - len(false_answers) - 1):
            self.options[len(false_answers) + 1 + j].setText("---")

        # Add the option indices.
        for (index, option) in enumerate(self.options):
            option.setText("%d) %s" % (index + 1, option.text()))
            option.setStyleSheet(self.ANSWER_STYLE)

        if (card.queue == 0) and (card.id not in self.new_cards):
            # It's a completely new card.
            self.state = self.STATE_NEW
            self.options[self.correct_answer].setStyleSheet(
                self.ANSWER_STYLE_CORRECT)
            self.timerLabel.setText("NEW!")
            self.new_cards.append(card.id)
        else:
            # Start the answer timer.
            self.state = self.STATE_COUNTDOWN
            self.timer.start(1000)


    def _updateTimerText(self) -> None:
        m = self.time_left_sec // 60
        s = self.time_left_sec % 60
        self.timerLabel.setText("%02d:%02d" % (m, s))
        self.timerLabel.setStyleSheet(self.TIMER_STYLE_GREEN)

    
    def _showDone(self) -> None:
        self.timer.stop()
        self.state = self.STATE_DONE
        self.timerLabel.setText("DONE!")
        self.timerLabel.setStyleSheet(self.TIMER_STYLE_GREEN)
        self.wordLabel.setText("")
        self.readingLabel.setText("")
        for option in self.options:
            option.setText("")
            option.setStyleSheet(self.ANSWER_STYLE)

    
    # This will be called by the timer object.
    def _on_timer(self) -> None:
        if self.state == self.STATE_COUNTDOWN:
            self.time_left_sec -= 1
            if self.time_left_sec <= 0:
                self.time_left_sec = 0
            self._updateTimerText()
            if self.time_left_sec == 0:
                self.timer.stop()
                self.timerLabel.setStyleSheet(self.TIMER_STYLE_RED)
                self.timerLabel.setText("TIMEOUT!")
                self._mark_again()
                self._showAnswer()
        elif self.state == self.STATE_ANSWER:
            self._showNextCard()
    

    def _showAnswer(self) -> None:
        # Highlight the right answer.
        self.options[self.correct_answer].setStyleSheet(
                self.ANSWER_STYLE_CORRECT)
        
        self.state = self.STATE_ANSWER
        self.timer.start(self.RESULT_TIMER_MS)


    def _selectAnswer(self, index) -> None:
        self.timer.stop()

        if index != self.correct_answer:
            self._mark_again()
            self.timerLabel.setStyleSheet(self.TIMER_STYLE_RED)
            if index < 0:
                self.timerLabel.setText("DONT KNOW!")
            elif index < len(self.options):
                self.timerLabel.setText("WRONG!")
                self.options[index].setStyleSheet(
                        self.ANSWER_STYLE_WRONG)
        else:
            self.timerLabel.setText("CORRECT!")
            self._mark_correct()
            self.timerLabel.setStyleSheet(self.TIMER_STYLE_GREEN)
            
        self._showAnswer()


    def _mark_correct(self) -> None:
        mw.col.sched.answerCard(self.current_card, 3)


    def _mark_again(self) -> None:
        mw.col.sched.answerCard(self.current_card, 1)


def startLazyAnki() -> None:
    # Get the active deck.
    active_deck = mw.col.decks.active
    if active_deck is None:
        showInfo("Please select a deck first!")
        return

    # Create and show LazyAnki window.
    mw.lazyAnkiWnd = wnd = LazyAnkiWnd()
    wnd.show()
    

def initLazyAnki() -> QAction:
    # Start LazyAnki action
    startAction = QAction("Start LazyAnki", mw)
    qconnect(startAction.triggered, startLazyAnki)
    mw.form.menuTools.addAction(startAction)
