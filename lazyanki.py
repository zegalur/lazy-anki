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

from enum import Enum

import random


class PlayerMode(Enum):
    MEANING_ONLY = 1
    READING_MEANING = 2
    #KANJI_MODE = 3


class PlayerState(Enum):
    INITIAL = 1
    COUNTDOWN = 2
    ANSWER = 3
    DONE = 4
    NEW = 5


class LazyAnkiWnd(QWidget):
    def __init__(self, parent=None, mode=PlayerMode.MEANING_ONLY):
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
        self.RESULT_CORRECT_MS = config['default_correct_time_ms']
        self.RESULT_FAILED_MS = config['default_failed_time_ms']
        self.time_left_sec = 0

        self.correct_answer = -1
        self.new_cards = []
        self.mode = mode
        self.state = PlayerState.INITIAL
        self.test_meaning = False
        self.prev_correct = False

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
        meanings = []
        readings = []
        for deck_id in active_deck_ids:
            deck = mw.col.decks.get(deck_id)
            deck_card_ids = mw.col.find_cards('"deck:%s"'%(deck["name"]))
            for card_id in deck_card_ids:
                note = mw.col.get_card(card_id).note()
                # Check if note has all the essential fields:
                if self.MEANING_FIELD not in note:
                    t = self.timerLabel.text()
                    self.timerLabel.setText( t + "\n\nError:\n" +
                            "A note without the meaning field" +
                            (" `{}`.".format(self.MEANING_FIELD)) )
                    return
                if self.READING_FIELD not in note:
                    t = self.timerLabel.text()
                    self.timerLabel.setText( t + "\n\nError:\n" + 
                            "A note without the reading field" +
                            (" `{}`.".format(self.READING_FIELD)) )
                    return
                if self.WORD_FIELD not in note:
                    t = self.timerLabel.text()
                    self.timerLabel.setText( t + "\n\nError:\n" + 
                            "A note without the word field" + 
                            (" `{}`.".format(self.WORD_FIELD)) )
                    return
                # Add this card into meanings and readings:
                meanings.append(note[self.MEANING_FIELD])
                readings.append(note[self.READING_FIELD])

        if len(meanings) == 0:
            t = self.timerLabel.text()
            self.timerLabel.setText( t + "\n\nError:\n" + 
                    "An empty deck or loading error.\n" +
                    "Please, close this window, select\n" + 
                    "a deck and try again." )
            return

        self.meanings_set = set(meanings)
        self.readings_set = set(readings)

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
        if self.state in [PlayerState.DONE, PlayerState.INITIAL]:
            super().keyPressEvent(event)
            return

        scan_code = event.key()

        if self.state == PlayerState.COUNTDOWN:
            if scan_code >= aqt.Qt.Key.Key_0:
                if scan_code <= self.OPTION_COUNT + aqt.Qt.Key.Key_0:
                    self._selectAnswer(scan_code - aqt.Qt.Key.Key_1)

        if self.state == PlayerState.NEW:
            if scan_code in [aqt.Qt.Key.Key_Enter, aqt.Qt.Key.Key_Return]:
                self._showNextCard()

        super().keyPressEvent(event)


    def _showNextCard(self) -> None:
        show_reading = True
        if self.mode == PlayerMode.READING_MEANING:
            show_reading = self.test_meaning

        answ_set = self.readings_set
        answ_field = self.READING_FIELD
        
        # Reset the timer.
        self.timer.stop()
        self.time_left_sec = self.TIMER_SEC
        self._updateTimerText()
        
        if self.test_meaning == False:
            self.current_card = mw.col.sched.getCard()
            if not self.current_card:
                self._showDone()
                return
        else:
            # Continue with previously loaded card
            answ_set = self.meanings_set
            answ_field = self.MEANING_FIELD

        card = self.current_card
        note = card.note()
        self.wordLabel.setText(note[self.WORD_FIELD])
        new_card = False

        # Check if this is a new card:
        if (card.queue == 0) and (card.id not in self.new_cards):
            new_card = True
            if self.mode == PlayerMode.READING_MEANING:
                answ_set = self.meanings_set
                answ_field = self.MEANING_FIELD

        # Get the audio (when available).
        self.audio_file = ""
        if self.AUDIO_FIELD in note:
            audio = note[self.AUDIO_FIELD]
            self.audio_file = audio.removeprefix("[sound:").removesuffix("]")
            if self.mode == PlayerMode.MEANING_ONLY or self.test_meaning:
                aqt.sound.av_player.play_file(self.audio_file)

        # Get some random false answers.
        false_answers = []
        tmp_copy = answ_set.copy()
        tmp_copy.remove(note[answ_field])
        for i in range(self.OPTION_COUNT - 1):
            if len(tmp_copy) == 0:
                break
            new_false_answer = list(tmp_copy)[random.randint(0, len(tmp_copy) - 1)]
            false_answers.append(new_false_answer)
            tmp_copy.remove(new_false_answer)

        # Set the correct answer.
        self.correct_answer = random.randint(0, len(false_answers))
        self.options[self.correct_answer].setText(note[answ_field])

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

        if new_card:
            # Show it as a completely new card.
            self.state = PlayerState.NEW
            self.options[self.correct_answer].setStyleSheet(
                self.ANSWER_STYLE_CORRECT)
            self.timerLabel.setText("NEW!")
            self.new_cards.append(card.id)
            show_reading = True
            if self.mode == PlayerMode.READING_MEANING:
                aqt.sound.av_player.play_file(self.audio_file)

        if show_reading:
            self.readingLabel.setText(note[self.READING_FIELD])
        else:
            self.readingLabel.setText("")

        if not new_card:
            # Start the answer timer if card is not a new card:
            self.state = PlayerState.COUNTDOWN
            self.timer.start(1000)

    def _updateTimerText(self) -> None:
        m = self.time_left_sec // 60
        s = self.time_left_sec % 60
        self.timerLabel.setText("%02d:%02d" % (m, s))
        self.timerLabel.setStyleSheet(self.TIMER_STYLE_GREEN)

    
    def _showDone(self) -> None:
        self.timer.stop()
        self.state = PlayerState.DONE
        self.timerLabel.setText("DONE!")
        self.timerLabel.setStyleSheet(self.TIMER_STYLE_GREEN)
        self.wordLabel.setText("")
        self.readingLabel.setText("")
        for option in self.options:
            option.setText("")
            option.setStyleSheet(self.ANSWER_STYLE)

    
    # This will be called by the timer object.
    def _on_timer(self) -> None:
        if self.state == PlayerState.COUNTDOWN:
            self.time_left_sec -= 1
            if self.time_left_sec <= 0:
                self.time_left_sec = 0
            self._updateTimerText()
            if self.time_left_sec == 0:
                self.timer.stop()
                self.timerLabel.setStyleSheet(self.TIMER_STYLE_RED)
                self.timerLabel.setText("TIMEOUT!")
                self._mark_again()
                self._showAnswer(is_correct=False)
        elif self.state == PlayerState.ANSWER:
            self._showNextCard()
    

    def _showAnswer(self, is_correct) -> None:
        # Highlight the right answer.
        self.options[self.correct_answer].setStyleSheet(
                self.ANSWER_STYLE_CORRECT)
        
        # Change the current state.
        self.state = PlayerState.ANSWER

        # Start the results timer. Timer durations depends on whether 
        # the answer was correct or incorrect.
        if is_correct:
            self.timer.start(self.RESULT_CORRECT_MS)
        else:
            self.timer.start(self.RESULT_FAILED_MS)


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
            
        self._showAnswer(is_correct=(index == self.correct_answer))


    def _mark_correct(self) -> None:
        if self.mode == PlayerMode.MEANING_ONLY:
            mw.col.sched.answerCard(self.current_card, 3)
        elif self.mode == PlayerMode.READING_MEANING:
            if self.test_meaning == True:
                self.test_meaning = False
                if self.prev_correct == True:
                    mw.col.sched.answerCard(self.current_card, 3)
                else:
                    mw.col.sched.answerCard(self.current_card, 1)
            else:
                self.test_meaning = True
                self.prev_correct = True


    def _mark_again(self) -> None:
        if self.mode == PlayerMode.MEANING_ONLY:
            mw.col.sched.answerCard(self.current_card, 1)
        elif self.mode == PlayerMode.READING_MEANING:
            if self.test_meaning == True:
                self.test_meaning = False    
                mw.col.sched.answerCard(self.current_card, 1)
            else:
                self.test_meaning = True
                self.prev_correct = False


def startLazyAnki(mode) -> None:
    # Get the active deck.
    active_deck = mw.col.decks.active
    if active_deck is None:
        showInfo("Please select a deck first!")
        return

    # Create and show LazyAnki window.
    mw.lazyAnkiWnd = wnd = LazyAnkiWnd(mode=mode)
    wnd.show()
    

def initLazyAnki() -> QAction:
    # Start LazyAnki action

    subMenu = QMenu("LazyAnki", mw)
    meaningOnly = QAction("Meaning Only...", subMenu)
    readingMeaning = QAction("Reading + Meaning...", subMenu)

    qconnect(meaningOnly.triggered, 
             lambda:startLazyAnki(PlayerMode.MEANING_ONLY))
    qconnect(readingMeaning.triggered, 
             lambda:startLazyAnki(PlayerMode.READING_MEANING))

    subMenu.addAction(meaningOnly)
    subMenu.addAction(readingMeaning)
    mw.form.menuTools.addMenu(subMenu)

