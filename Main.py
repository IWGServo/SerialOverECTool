# gui.py

import tkinter as tk
from threading import Thread
from ecat_slave import Master  # Import the Master class from ethercat.py
#change for exampledfsdfsdf
def on_enter_pressed(event):
    user_input = entry.get()
    if user_input:

        
        res=master.mySlaves[0].test_SerialOverEcat(user_input)

        # Example: Use the EtherCAT Master instance to process input
        # response = process_input(user_input)  # Modify as needed
        # text_area.insert(tk.END, f"You: {user_input}\n")
        text_area.insert(tk.END, f"{res}\n")
        entry.delete(0, tk.END)
        text_area.see(tk.END)  # Scroll to the end of the text area

def process_input(user_input):
    # Example: Process input and return a response
    return f"You said: {user_input}"
def close_com():
    # Ensure to use the global master variable and call the appropriate method
    if master is not None:
        master.mySlaves[0].writeSDO(0x20E0, 2, 0)
def run_gui():
    global entry, text_area
    # Set up the main window
    root = tk.Tk()
    root.title("Simple Terminal")
    # Set up the frame for text_area and scrollbar
    frame = tk.Frame(root)
    frame.pack(pady=10)
    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Set up the text area (output) and link the scrollbar
    text_area = tk.Text(frame, height=40, width=150, yscrollcommand=scrollbar.set)
    text_area.pack(side=tk.LEFT)
    scrollbar.config(command=text_area.yview)
    button = tk.Button(root, text="Close Com", command=close_com)
    button.pack(pady=5)
    # Set up the entry widget (input)
    entry = tk.Entry(root,width=100)
    entry.pack(pady=5)
    entry.bind("<Return>", on_enter_pressed)

    root.mainloop()

if __name__ == "__main__":
    # Start GUI in a separate thread
    gui_thread = Thread(target=run_gui)
    gui_thread.start()

    # Example of using the EtherCAT Master
    master = Master()
    while not master.connection_status:
        master = Master()
    master.setUpSlaves()

    # Do other EtherCAT tasks as needed
    # ...
    # Join GUI thread when done
    gui_thread.join()
