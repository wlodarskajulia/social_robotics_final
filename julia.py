from autobahn.twisted.component import Component, run
from autobahn.twisted.util import sleep
from google import genai
from google.genai import types
from twisted.internet.defer import inlineCallbacks
from alpha_mini_rug import perform_movement

from robot_prompt import prompt_for_robot

import re

API_KEY = "AIzaSyCr5L0bpehbvhOVoFONEUblW07hxGusQjk"
# Setting the API KEY
chatbot = genai.Client(api_key=API_KEY)

# Sytem Instructions for the chatbot. This is a prompt that tells the chatbot how to respond to the user.
# SYSTEM_INSTRUCTION = prompt_for_robot
SYSTEM_INSTRUCTION = "Have a basic conversation with the user. Ask about the weather, day, name. Keep your responses up to 10 words."
conversation = []

# Gemini configuration reused across calls
GEMINI_CONFIG = types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)

exit_conditions = (":q", "quit", "exit")

# Global flags to coordinate between the main loop and the asr function
finish_dialogue = False  # Indicates when a full utterance is ready
query = ""  # Stores the utterance
debug_list = []  # Stores the actions happening during the experiment


def print_debug_list(list_to_print: list[str]):
    for i, element in enumerate(list_to_print):
        print(i, element)


def asr(frames: dict):
    """
    ASR callback function which get triggered every time the user is done speaking.
    Sets speech to text.
    """
    global finish_dialogue
    global query
    if frames["data"]["body"]["final"]:
        query = str(frames["data"]["body"]["text"]).strip()
        if len(query.split()) < 1:  # ignore empty queries
            return
        print("ASR response: ", query)
        finish_dialogue = True

def parse_text(text: str) -> list[tuple[str, str]]:
    # list[tuple[label, text_to_say]]
    # labels = [TRIGGER1, ..., TRIGGER5, NO_TRIGGER]
    # In the text, the trigger has to be in front of the statement that we want to trigger
    # e.g. "TRIGGER1 Hi my name is Julia! TRIGGER2 Could you specify that? TRIGGER2 If not that bye"

    trigger_words = ["NOD", "SHAKE", "THINK", "POINT", "WAVE"]
    indexed_text = []

    # Split the text into words
    words = text.split()
    current_segment = []
    current_label = "NO_TRIGGER"

    for word in words:
        if word in trigger_words:
            # If we have accumulated words, save them with the previous label
            if current_segment:
                indexed_text.append((current_label, " ".join(current_segment)))
                current_segment = []
            # Start new segment with the trigger label
            current_label = word
        else:
            current_segment.append(word)
    
    # Append the last segment
    if current_segment:
        indexed_text.append((current_label, " ".join(current_segment)))
    
    return indexed_text


class RobotMovements:
    def __init__(self, session):
        self.session = session
        self.tag_map = {
            "NOD": "nod",
            "SHAKE": "shake_head",
            "WAVE": "wave",
            "THINK": "think",
            "POINT": "point",
        }
        self.text = None

    @inlineCallbacks
    def nod(self):
        """Triggered by NOD"""
        debug_list.append("nod() called")
        print(" want to nod")
        perform_movement(
            self.session,
            frames=[
                {"time": 400, "data": {"body.head.pitch": 0.15}},
                {"time": 1200, "data": {"body.head.pitch": -0.15}},
                {"time": 2000, "data": {"body.head.pitch": 0.15}},
                {"time": 2400, "data": {"body.head.pitch": 0.0}},
            ],
            force=True,
        )
        yield self.session.call("rie.dialogue.say", text=self.text)

    @inlineCallbacks
    def shake_head(self):
        """Triggered by SHAKE"""
        debug_list.append("shake_head() called")
        print(" want to shake")
        perform_movement(
            self.session,
            frames=[
                {"time": 400, "data": {"body.head.yaw": 0.5}},
                {"time": 1200, "data": {"body.head.yaw": -0.5}},
                {"time": 2000, "data": {"body.head.yaw": 0.5}},
                {"time": 2400, "data": {"body.head.yaw": 0.0}},
            ],
            force=True,
        )
        yield self.session.call("rie.dialogue.say", text=self.text)

    @inlineCallbacks
    def wave(self):
            """Triggered by WAVE"""
            debug_list.append("wave() called")
            print("I want to wave")
            perform_movement(
                self.session,
                frames=[{"time": 612.44, "data": {"body.arms.left.upper.pitch": -2.1}}],
                force=True,
            )
            perform_movement(
                self.session,
                frames=[
                    {"time": 612.44, "data": {"body.arms.left.lower.roll": -0.6}},
                    {"time": 854, "data": {"body.arms.left.lower.roll": -0.8}},
                    {"time": 1300, "data": {"body.arms.left.lower.roll": -0.2}},
                    {"time": 1715, "data": {"body.arms.left.lower.roll": -0.8}},
                    {"time": 2120, "data": {"body.arms.left.lower.roll": -0.2}},
                ],
                force=True,
            )
            yield self.session.call("rie.dialogue.say", text=self.text)

    @inlineCallbacks
    def think(self):
        """Triggered by THINK"""
        debug_list.append("think() called")
        # perform_movement ...
        yield self.session.call("rie.dialogue.say", text=self.text)

    @inlineCallbacks
    def point(self):
        """Triggered by POINT"""
        debug_list.append("point() called")
        print(" want to point")
        perform_movement(
            self.session,
            frames=[
                {"time": 400, "data": {
                    "body.torso.yaw": 0.500, 
                    "body.arms.left.upper.pitch": -0.59}},
                {"time": 1200, "data": {
                    "body.arms.left.lower.roll": -1.70, 
                    "body.arms.right.upper.pitch": 1.00}},
                {"time": 2000, "data": {
                    "body.arms.left.lower.roll": 0.0, 
                    "body.arms.right.upper.pitch": 0.0}},
                {"time": 2400, "data": {
                    "body.torso.jaw": 0.0, 
                    "body.arms.left.upper.pitch": 0.0}}
            ],
            force=True      
        )
        yield self.session.call("rie.dialogue.say", text=self.text)

    @inlineCallbacks
    def perform_based_on_tags(self, response_text: str):
        debug_list.append(
            f"perform_based_on_tags() called, response_text: {response_text}"
        )
        for tag, method_name in self.tag_map.items():
            if tag in response_text:
                self.text = response_text
                debug_list.append(f"I found this tag: {tag}")
                yield getattr(self, method_name)()

    @inlineCallbacks
    def perform_tag(self, response_text: str, tag: str):
        # DOES IT WORK
        self.text = response_text
        debug_list.append(f"I found this tag: {tag}")
        method_name = self.tag_map[tag]
        yield getattr(self, method_name)()

    def strip_response_text(self, response_text: str):
        for tag in self.tag_map:
            if tag in response_text:
                response_text = re.sub(tag, "", response_text)
        debug_list.append(
            f"strip_response_text() executed, new response: {response_text}"
        )
        return response_text.strip()

class RobotFaceTracking:
    """Handle face detection and tracking."""

    def __init__(self, session):
        self.session = session

    @inlineCallbacks
    def find_face(self):
        # Look for a face
        print("I start looking for a face")
        yield self.session.call("rie.vision.face.find")
        # Greet when face is found
        yield self.session.call("rie.dialogue.say", text="Hi! I see you!")
        # Start tracking
        yield self.session.call("rie.vision.face.track")

    @inlineCallbacks
    def track_face(self):
        # Start tracking face continuously
        print("I am tracking")
        yield self.session.call("rie.vision.face.track")

    @inlineCallbacks
    def stop_tracking(self):
        yield self.session.call("rie.vision.face.track.stop")

def speak(session, text: str):
    # list[tuple[label, text]]
    # labels = [NOD, ..., POINT, NO_TRIGGER]
    indexed_text = parse_text(text)
    movements = RobotMovements(session)
    for element in indexed_text:
        label, text_to_say = element
        if label == "NO_TRIGGER":
            yield session.call("rie.dialogue.say_animated", text=text_to_say)
        else:
            yield movements.perform_tag(text_to_say, label)
            yield sleep(5)


@inlineCallbacks
def main(session, details):
    """
    Main dialogue loop for the robot's setup and responses
    """
    global finish_dialogue, query, response
    yield session.call("rie.dialogue.config.language", lang="en")
    yield session.call("rom.optional.behavior.play", name="BlocklyStand")

    movements = RobotMovements(session)
    #face_track = RobotFaceTracking(session)

    # Start face detection and tracking
    #yield face_track.find_face()

    # Prompt from the robot to the user to say something
    intro_text = "NO_TRIGGER Hi, I am Mini. Let's solve the mystery together!"
    speak(session, intro_text)

    yield session.subscribe(asr, "rie.dialogue.stt.stream")
    yield session.call("rie.dialogue.stt.stream")

    # While user did not say exit or quit
    dialogue = True
    while dialogue:
        if finish_dialogue:
            # Handle explicit exit commands
            if query in exit_conditions:
                dialogue = False
                speak(session, "OK, I will leave you then.")
                break

            # Handle valid user input
            elif query != "":
                # Stop the STT to avoid capturing robot speech
                yield session.call("rie.dialogue.stt.close")

                # Append the message to the conversation history
                conversation.append(
                    types.Content(role="user", parts=[types.Part(text=query)])
                )

                # Generate response from Gemini
                response = chatbot.models.generate_content(
                    model="gemini-2.5-flash", contents=conversation
                )

                response_from_robot = response.text

                # Add the model's response to conversation memory
                conversation.append(
                    types.Content(
                        role="model", parts=[types.Part(text=response_from_robot)]
                    )
                )

                test_response = "WAVE hello, nice to see you"
                print("he should wave")
                speak(session, test_response)
                # speak(session, response_from_robot)

            else:  # Edge case, empty dialogue
                yield session.call("rie.dialogue.stt.close")
                speak(session, "NO_TRIGGER Sorry, what did you say?")

            # Reset global flags
            finish_dialogue = False
            query = ""

            # Print and clear debug list each turn
            print_debug_list(debug_list)
            debug_list.clear()

            # Prevent immediate re-entering the loop
            yield sleep(0.2)
            yield session.call("rie.dialogue.stt.stream")

        # Keep the STT stream active
        yield session.call("rie.dialogue.stt.stream")

    # Close the STT stream
    yield session.call("rie.dialogue.stt.close")
    # Let the robot crouch
    yield session.call("rom.optional.behavior.play", name="BlocklyCrouch")
    session.leave()


wamp = Component(
    transports=[
        {
            "url": "ws://wamp.robotsindeklas.nl",
            "serializers": ["msgpack"],
            "max_retries": 0,
        }
    ],
    realm="rie.699ee4a05c33d0f8536fead0",
)

wamp.on_join(main)

if __name__ == "__main__":
    run([wamp])
