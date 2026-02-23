from autobahn.twisted.component import Component, run
from autobahn.twisted.util import sleep
from google import genai
from google.genai import types
from twisted.internet.defer import inlineCallbacks

from robot_prompt import prompt_for_robot

import re

API_KEY = "set_your_API_KEY"
# Setting the API KEY
chatbot = genai.Client(api_key=API_KEY)

# Sytem Instructions for the chatbot. This is a prompt that tells the chatbot how to respond to the user.
SYSTEM_INSTRUCTION = prompt_for_robot
conversation = []

# Gemini configuration reused across calls
GEMINI_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_INSTRUCTION
)

exit_conditions = (":q", "quit", "exit")

# Global flags to coordinate between the main loop and the asr function
finish_dialogue = False # Indicates when a full utterance is ready
query = "" # Stores the utterance
debug_list = [] # Stores the actions happening during the experiment

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
        if len(query.split()) < 1: #ignore empty queries
            return
        print("ASR response: ", query)
        finish_dialogue = True

class RobotMovements:
    def __init__(self, session):
        self.session = session
        self.tag_map = {
            "TRIGGER1": "nod",
            "TRIGGER2": "shake_head",
            "TRIGGER3": "wave",
            "TRIGGER4": "think"
        }
    def nod(self):
        """Triggered by TRIGGER1"""
        debug_list.append("nod() called")

    def shake_head(self):
        """Triggered by TRIGGER2"""
        debug_list.append("shake_head() called")

    def wave(self):
        """Triggered by TRIGGER3"""
        debug_list.append("wave() called")

    def think(self):
        """Triggered by TRIGGER4"""
        debug_list.append("think() called")

    def perform_based_on_tags(self, response_text: str):
        debug_list.append(f"perform_based_on_tags() called, response_text: {response_text}")
        for tag, method_name in self.tag_map.items():
            if tag in response_text:
                debug_list.append(f"I found this tag: {tag}")
                getattr(self, method_name)()
        
    def strip_response_text(self, response_text: str):
        for tag in self.tag_map:
            if tag in response_text:
                response_text = re.sub(tag, "", response_text)
        debug_list.append(f"strip_response_text() executed, new response: {response_text}")
        return response_text.strip()

@inlineCallbacks
def main(session, details):
    """
    Main dialogue loop for the robot's setup and responses
    """
    global finish_dialogue, query, response
    yield session.call("rie.dialogue.config.language", lang="en")
    yield session.call("rom.optional.behavior.play",name="BlocklyStand")

    movements = RobotMovements(session)

    # Prompt from the robot to the user to say something
    intro_text = "Hi, I am Mini. Let's solve the mystery together!"
    movements.perform_based_on_tags(intro_text)
    yield session.call("rie.dialogue.say_animated", text=movements.strip_response_text(intro_text))

    
    yield session.subscribe(asr, "rie.dialogue.stt.stream")
    yield session.call("rie.dialogue.stt.stream")

    # While user did not say exit or quit
    dialogue = True
    while dialogue:
        if (finish_dialogue):

            # Handle explicit exit commands
            if query in exit_conditions:
                dialogue = False
                yield session.call("rie.dialogue.say_animated", text="Ok, I will leave you then")
                break

            # Handle valid user input
            elif (query != ""):
                # Stop the STT to avoid capturing robot speech
                yield session.call("rie.dialogue.stt.close")

                # Append the message to the conversation history
                conversation.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text=query)]
                    )
                )

                # Generate response from Gemini
                response = chatbot.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=conversation
                )

                response_from_robot = response.text

                # Add the model's response to conversation memory
                conversation.append(
                    types.Content(
                        role="model",
                        parts=[types.Part(text=response_from_robot)]
                    )
                )

                # Fire movement in parallel, then speak
                movements.perform_based_on_tags(response_from_robot)
                response_text = movements.strip_response_text(response_from_robot)
                yield session.call("rie.dialogue.say_animated", text=response_text)

            else: # Edge case, empty dialogue
                yield session.call("rie.dialogue.stt.close")
                yield session.call("rie.dialogue.say_animated", text="Sorry, what did you say?")

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
    yield session.call("rom.optional.behavior.play",name="BlocklyCrouch")
    session.leave()

wamp = Component(
    transports=[{
        "url": "ws://wamp.robotsindeklas.nl",
        "serializers": ["msgpack"],
        "max_retries": 0
    }],
    realm="rie.69945b7ae14c6bd0843c6857",
)

wamp.on_join(main)

if __name__ == "__main__":
    run([wamp])