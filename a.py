import cv2
import numpy as np
from mss import mss
import time
import threading
from pynput import keyboard
import os
import pyautogui

# Define global variables
recording = False
sct = mss()  # Screen capture object
output_folder = "messenger_frames"
frame_count = 0
capture_thread = None
region = None  # Will store the messenger video region

# Create output folder if it doesn't exist
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

def select_messenger_region():
    """Automatically detect the messenger video region by looking for worker elements"""
    global region
    
    print("Searching for Messenger video call window...")
    
    # Take a screenshot of the entire screen
    screenshot = np.array(sct.grab(sct.monitors[0]))
    
    # Convert to grayscale for easier processing
    gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
    
    # Try to find Messenger's blue color (common in their UI) or worker text elements
    # This is a simple approach - you might need to adjust these values
    messenger_blue_lower = np.array([0, 120, 220])  # BGR values
    messenger_blue_upper = np.array([60, 170, 255])
    
    # Convert screenshot to proper format for color detection
    bgr_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGBA2BGR)
    mask = cv2.inRange(bgr_screenshot, messenger_blue_lower, messenger_blue_upper)
    
    # Find contours in the mask
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter contours by size - video call windows are typically larger
    min_area = 50000  # Adjust based on your screen resolution
    valid_contours = [cnt for cnt in contours if cv2.contourArea(cnt) > min_area]
    
    if valid_contours:
        # Find the largest contour which is likely the video call window
        largest_contour = max(valid_contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)
        region = (x, y, w, h)
        print(f"Messenger video region detected: {region}")
        
        # Draw the region on the screenshot for visualization
        result = bgr_screenshot.copy()
        cv2.rectangle(result, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.imshow("Detected Messenger Region", result)
        cv2.waitKey(3000)  # Show for 3 seconds
        cv2.destroyAllWindows()
    else:
        print("Could not automatically detect Messenger video region.")
        print("Please select the region manually...")
        
        # Fall back to manual selection if automatic detection fails
        region = pyautogui.selectROI("Select Messenger Video", 
                                    screenshot, 
                                    fromCenter=False, 
                                    showCrosshair=True)
        cv2.destroyWindow("Select Messenger Video")
    
    if sum(region) == 0:
        print("No region selected. Will capture the entire screen.")
        region = None
    else:
        print(f"Selected region: {region}")
    
    return region

def capture_frames():
    global recording, frame_count, region
    
    # Create a new MSS instance for this thread
    with mss() as thread_sct:
        while recording:
            try:
                # If region is set, use it, otherwise use the monitor
                if region:
                    x, y, width, height = region
                    capture_area = {
                        "left": x,
                        "top": y,
                        "width": width,
                        "height": height
                    }
                else:
                    capture_area = monitor
                
                # Capture the selected region or entire monitor
                screenshot = thread_sct.grab(capture_area)
                if screenshot is None:
                    print("Error: Screenshot capture failed.")
                    break

                # Convert to numpy array (BGR format for OpenCV)
                frame = np.array(screenshot)
                # Convert RGBA to BGR
                frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

                # Save the frame
                frame_filename = os.path.join(output_folder, f"frame_{frame_count:04d}.jpg")
                success = cv2.imwrite(frame_filename, frame)
                if success:
                    print(f"Saved {frame_filename}")
                    frame_count += 1
                else:
                    print(f"Failed to save {frame_filename}")

                # Control frame rate (1 FPS to reduce load)
                time.sleep(1.0)

            except Exception as e:
                print(f"Error during capture: {e}")
                recording = False
                break

def start_capture():
    global capture_thread
    if capture_thread is None or not capture_thread.is_alive():
        capture_thread = threading.Thread(target=capture_frames)
        capture_thread.start()

# Keyboard listener functions
def on_press(key):
    global recording, region
    try:
        if key.char == 'r':  # Press 'r' to select region
            region = select_messenger_region()
        elif key.char == 's':  # Press 's' to start
            if not recording:
                recording = True
                if region:
                    print(f"Started capturing region: {region}")
                else:
                    print(f"Started capturing full monitor: {monitor['width']}x{monitor['height']}")
                start_capture()
        elif key.char == 'q':  # Press 'q' to stop
            recording = False
            print("Stopped capturing frames.")
            return False  # Stop listener
    except AttributeError:
        pass

# Select primary monitor
print("Available monitors:", sct.monitors)
try:
    monitor = sct.monitors[1]  # Primary monitor
    print(f"Selected monitor: {monitor['width']}x{monitor['height']} at ({monitor['left']}, {monitor['top']})")
except IndexError:
    print("Error: No monitor found at index 1. Falling back to first monitor.")
    monitor = sct.monitors[0]

# Set up the keyboard listener
listener = keyboard.Listener(on_press=on_press)
listener.start()

# Keep the script running until 'q' is pressed
print("Press 'r' to select messenger video region")
print("Press 's' to start capturing, 'q' to stop.")
listener.join()

# Cleanup
if capture_thread is not None:
    capture_thread.join()
cv2.destroyAllWindows()