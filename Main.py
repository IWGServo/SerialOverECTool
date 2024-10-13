# gui.py

import tkinter as tk
from threading import Thread
from ecat_slave import Master  # Import the Master class from ecat_slave.py

def on_enter_pressed(event):
    global master  # Declare master as global
    user_input = entry.get()
    if user_input:
        res = master.mySlaves[0].test_SerialOverEcat(user_input)
        text_area.insert(tk.END, f"{res}\n")
        entry.delete(0, tk.END)
        text_area.see(tk.END)  # Scroll to the end of the text area

def close_com():
    global master  # Declare master as global to access it
    if master is not None:
        master.mySlaves[0].writeSDO(0x20E0, 2, 0)

def run_gui():
    global entry, text_area
    # Set up the main window
    root = tk.Tk()  # Corrected the syntax error
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

    # Close Com button
    button = tk.Button(root, text="Close Com", command=close_com)
    button.pack(pady=5)

    # Set up the entry widget (input)
    entry = tk.Entry(root, width=100)
    entry.pack(pady=5)
    entry.bind("<Return>", on_enter_pressed)

    root.mainloop()

def setup_master():
    global master
    # Create the master instance
    master = Master()
    while not master.connection_status:
        master.connectSlaves()  # Recreate the master if connection fails
    master.setUpSlaves()

if __name__ == "__main__":
    # Start the GUI in a separate thread
    gui_thread = Thread(target=run_gui)
    gui_thread.start()

    # Setup the EtherCAT Master
    setup_master()

    # Optionally join the GUI thread when done
    gui_thread.join()
