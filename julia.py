from alpha_mini_rug import perform_movement
from autobahn.twisted.component import Component, run
from autobahn.twisted.util import sleep
from google import genai
from google.genai import types
from twisted.internet.defer import inlineCallbacks

import random
import re

API_KEY = "set_your_API_KEY"
# Setting the API KEY
chatbot = genai.Client(api_key=API_KEY)

# Sytem Instructions for the chatbot. This is a prompt that tells the chatbot how to respond to the user.

SYSTEM_INSTRUCTION = """
#context
You are a friendly social robot and a fun game companion. You are
playing a game of 'With Other Words' (aka Taboo). You can take both
the director and matcher roles. As the director, you give clues for a
secret word without using the word itself. As the matcher, the user
gives you clues, and you must guess the word.

#user profile
The user is a general audience. The user may speak with small pauses or hesitation, so wait
patiently before responding.

#instructions
1. You start by asking the user if they want to play as the director
or the matcher. The user can also choose to exit the game by saying 'exit' or 'quit'.

2. If the user chooses director, the user will then give you clues to
guess the secret word. Listen to the user's clues patiently and try to
guess the word accurately. If you guess the word correctly,
congratulate the user with a cheer or a joke and ask if they want to
play again or exit. If you guess incorrectly, encourage the user to
give more clues or try again. If the user gives up, ask if they want
to play again or exit.

3. If the user chooses a matcher, you will pick a secret word and give
creative clues without using the word itself or related forbidden
terms. When you first pick your secret word, include it in your response 
using this exact format on a new line: "SECRET_WORD: word".
If the user guesses the secret word correctly, congratulate them with
a cheer or a joke and ask if they want to play again or exit. If they
guess incorrectly, encourage them to try again or give additional
clues. If they clearly state that they give up, reveal the word, cheer
them up, and ask if they want to play again or exit.

4. The game continues until the secret word is correctly guessed or
the user decides to end the game by saying 'exit' or 'quit'.

#additional information
Throughout the game, you respond in a very brief, short, conversational,
approachable, and friendly style. Only speak when it is clearly your
turn. Wait for complete user clues before responding. Never reveal the
secret word unless clearly stated otherwise by the user. Never say "asterisk" nor pronounce "*". 
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

def generate_movement(text, delta_t=1.5):
    """
    Generates random, small movements for the robot based on estimated
    speech duration.
    
    Args:
        text (str): Text that the robot will speak.
        delta_t (float): Time step between movement frames in seconds.
    """
    # Estimate speech duration
    word_count = len(text.split())
    speech_duration = word_count * 0.2 # 0.2s per word

    n_frames = int(speech_duration / delta_t)
    frames = []

    for i in range(n_frames):
        # Head movements
        head_pitch = random.uniform(-0.09, 0.09)
        head_yaw   = random.uniform(-0.45, 0.45)
        head_roll = random.uniform(-0.09, 0.09)  

        # Arm movements
        right_arm = random.uniform(-1.5, 0) 
        left_arm = random.uniform(-1.5, 0) 

        frame = {
            "time": i * delta_t * 1000,  # miliseconds
            "data": {
                "body.head.pitch": head_pitch,
                "body.head.yaw": head_yaw,
                "body.head.roll": head_roll,
                "body.arms.right.upper.pitch": right_arm,
                "body.arms.left.upper.pitch": left_arm,
            }
        }
        frames.append(frame)

    return frames

@inlineCallbacks
def speak_with_movement(session, text):
    """
    Make the robot speak while performing movement.
    """
    # Estimate syllables for timing
    num_of_words = len(text.split())
    n_syllables = num_of_words * 1.5
    delta_t = 0.2
    M = 2

    # Generate frames
    frames_list = generate_movement(text, delta_t=delta_t)

    # Perform the micro-movements in parallel
    perform_movement(session, frames=frames_list, force=True)

    # Start speaking
    yield session.call("rie.dialogue.say", text=text)

    # Sleep to let movements complete
    yield sleep((n_syllables - M) * delta_t)

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
    yield speak_with_movement(session, intro_text)
    
    yield session.subscribe(asr, "rie.dialogue.stt.stream")
    yield session.call("rie.dialogue.stt.stream")

    # While user did not say exit or quit
    dialogue = True
    while dialogue:
        if (finish_dialogue):
            # Handle explicit exit commands
            if query in exit_conditions:
                dialogue = False
                yield speak_with_movement(session, "Ok, I will leave you then")
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
                yield speak_with_movement(session, response_text)
                yield session.call("rie.dialogue.stt.stream")

            else: # Edge case, empty dialogue
                yield session.call("rie.dialogue.stt.close")
                yield speak_with_movement(session, "Sorry, what did you say?")
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