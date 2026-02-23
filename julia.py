from autobahn.twisted.component import Component, run
from autobahn.twisted.util import sleep
from google import genai
from google.genai import types
from twisted.internet.defer import inlineCallbacks

import re

API_KEY = "set_your_API_KEY"
# Setting the API KEY
chatbot = genai.Client(api_key=API_KEY)

# Sytem Instructions for the chatbot. This is a prompt that tells the chatbot how to respond to the user.

SYSTEM_INSTRUCTION = """
You are a cooperaive collegue and together with user you share a common
goal to solve the task together. You must provide task-relevant hints when
appropriate and encourgae collaboration. You will be the one introducting the task
to the participant. Allow the user to solve many things by themselves, but also propose something.
You should act as if you are a companion on their level, so you can reach the conclusion together. 
"""

#Conversation history
conversation = [
    types.Content(
        role="user",
        parts=[types.Part(text=SYSTEM_INSTRUCTION)]
    )
]

exit_conditions = (":q", "quit", "exit")

# Global flags to coordinate between the main loop and the asr function
finish_dialogue = False # Indicates when a full utterance is ready
query = "" # Stores the utterance
robot_is_director = None # Tracks if robot is a director
secret_word = None # Stores the secret word when the robot is the director

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
        print("ASR response: ",query)
        finish_dialogue = True

@inlineCallbacks
def main(session, details):
    """
    Main dialogue loop for the robot's setup and responses
    """
    global finish_dialogue, query, response, robot_is_director, secret_word
    yield session.call("rie.dialogue.config.language", lang="en")
    yield session.call("rom.optional.behavior.play",name="BlocklyStand")

    # Prompt from the robot to the user to say something
    intro_text = "Hi, I am Mini. Do you want to play a game of 'With other Words' with me?"
    yield session.call("rie.dialogue.say_animated", text=intro_text)

    
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
                clue_1 = "SECRET_WORD:"

                if robot_is_director is True and secret_word is None and clue_1 in response_from_robot:
                    # Take everything after SECRET_WORD:
                    after_keyword = response_from_robot.split(clue_1, 1)[1]
                    # Extract only the first word after it
                    secret_word = after_keyword.strip().split()[0]
                    print(f"[DEBUG] Robot picked secret word: {secret_word}")

                # Add the model's response to conversation memory
                conversation.append(
                    types.Content(
                        role="model",
                        parts=[types.Part(text=response_from_robot)]
                    )
                )

                # Remove the SECRET_WORD line or inline occurrence completely
                response_text = re.sub(r"SECRET_WORD:\s*[^\s\n]+", "", response_from_robot)
                response_text = response_text.strip()

                # Close the microphone, speak the response, activate the microphone again
                yield session.call("rie.dialogue.stt.close")
                yield session.call("rie.dialogue.say_animated", text=response_text)
                yield session.call("rie.dialogue.stt.stream")

            else: # Edge case, empty dialogue
                yield session.call("rie.dialogue.stt.close")
                yield session.call("rie.dialogue.say_animated", text=response_text)
                yield session.call("rie.dialogue.stt.stream")

            # Reset global flags
            finish_dialogue = False
            query = ""
            # Prevent immediate re-entering the loop
            yield sleep(0.2)

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