import io
from obspy.core.utcdatetime import UTCDateTime
from obspy import read
from obspy import Stream, UTCDateTime
from obspy.signal.trigger import recursive_sta_lta, trigger_onset, plot_trigger
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton,
                             QDialog, QLineEdit, QDialogButtonBox, QFormLayout, QComboBox, QHBoxLayout
                             )
from obspy.clients.seedlink.easyseedlink import create_client
from obspy import UTCDateTime, Stream, read
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from obspy.signal.trigger import recursive_sta_lta
import sys
import json
import numpy as np
import pandas as pd
import platform
import subprocess
import threading
import pygame
import time



start = True
data_array = []


class Ui_MainWindow(object):
    # Sinyal baru untuk memperbarui plot
    dataChanged = pyqtSignal()

    def setupUi(self, MainWindow):
        self.data_array = data_array
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1300, 720)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.tabWidget = QtWidgets.QTabWidget(self.centralwidget)
        self.tabWidget.setGeometry(QtCore.QRect(0, 0, 1300, 650))
        self.tabWidget.setObjectName("tabWidget")
        self.tab = QWidget()
        self.tab.setObjectName("tab")
        self.tabWidget.addTab(self.tab, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName("tab_2")
        self.tabWidget.addTab(self.tab_2, "")
        MainWindow.setCentralWidget(self.centralwidget)

        self.setupTabWidget(MainWindow)

    def setupTabWidget(self, MainWindow):
        # Buttons
        self.start_button = QPushButton("Start", self.tab)
        self.stop_button = QPushButton("Stop", self.tab)
        self.add_station_button = QPushButton("Add Station", self.tab)
        self.remove_station_button = QPushButton("Remove Station", self.tab)

        # Connect buttons to functions
        self.start_button.clicked.connect(self.toggleStatusOn)
        self.stop_button.clicked.connect(self.toggleStatusOff)
        self.add_station_button.clicked.connect(self.add_station_dialog)
        self.remove_station_button.clicked.connect(self.remove_station_dialog)

        # Layout
        self.button_layout = QHBoxLayout()
        self.button_layout.addWidget(self.start_button)
        self.button_layout.addWidget(self.stop_button)
        self.button_layout.addWidget(self.add_station_button)
        self.button_layout.addWidget(self.remove_station_button)

        self.live_plot_widget = SeismicApp(data_array)
        self.live_plot_widget.start_seismic_thread()

        self.layout = QVBoxLayout(self.tab)
        self.layout.addLayout(self.button_layout)
        self.layout.addWidget(self.live_plot_widget)

        MainWindow.setWindowTitle("Seismic Data Viewer")

    def toggleStatusOn(self):
        global start
        start = True

    def toggleStatusOff(self):
        global start
        start = False

    def updateUI(self):
        # Clear the layout first
        self.clearLayout(self.layout)

        # Setup the tab widget again
        self.setupTabWidget(MainWindow)

    def clearLayout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                    # Setup the tab widget again
                    self.setupTabWidget(MainWindow)
                else:
                    self.clearLayout(item.layout())

    def add_station_dialog(self):
        dialog = AddStationDialog("Add Station")
        if dialog.exec_():
            server = list(dialog.server_options.keys())[
                dialog.DropdownServer.currentIndex()]
            network = dialog.networkLineEdit.text()
            station = dialog.stationLineEdit.text()
            location = dialog.locationLineEdit.text()
            channel = dialog.channelLineEdit.text()
            data_array.append(
                {"server": server, "network": network, "station": station, "location": location, "channel": channel})
            with open('data_array.json', 'w') as file:
                json.dump(data_array, file)
            self.updateUI()

    def remove_station_dialog(self):
        # Pass data_array to the dialog
        dialog = RemoveStationDialog("Remove Station", self.data_array)
        if dialog.exec_():
            network = dialog.DropdownNetwork.currentText()
            station = dialog.DropdownStation.currentText()
            channel = dialog.DropdownChannel.currentText()
            # Access data_array through self
            for i, data in enumerate(self.data_array):
                if data["network"] == network and data["station"] == station and data["channel"] == channel:
                    del self.data_array[i]
                    break
            with open('data_array.json', 'w') as file:
                json.dump(self.data_array, file)
            # Memancarkan sinyal setelah menghapus stasiun
            self.updateUI()


class AddStationDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)

        # Server options mapping
        self.server_options = {
            "geofon.gfz-potsdam.de": "Geofon",
            "rtserve.iris.washington.edu": "IRIS",
            "172.19.3.65": "BMKG"
        }
        self.location_options = {
            "": "",
            "00": "00"
        }

        layout = QFormLayout(self)
        self.DropdownServer = QComboBox()
        self.DropdownServer.addItems(self.server_options.values())
        layout.addRow("Server:", self.DropdownServer)
        self.networkLineEdit = QLineEdit()
        layout.addRow("Network:", self.networkLineEdit)
        self.stationLineEdit = QLineEdit()
        layout.addRow("Station:", self.stationLineEdit)
        self.locationLineEdit = QLineEdit()
        self.DropdownLoc = QComboBox()
        self.DropdownLoc.addItems(self.location_options.keys())
        layout.addRow("Location:", self.DropdownLoc)
        self.channelLineEdit = QLineEdit()
        layout.addRow("Channel:", self.channelLineEdit)

        buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)


class RemoveStationDialog(QDialog):
    def __init__(self, title, data_array, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.data_array = data_array
        self.network = ""
        self.station = ""
        self.channel = ""

        layout = QFormLayout(self)
        self.DropdownNetwork = QComboBox()
        self.DropdownStation = QComboBox()
        self.DropdownChannel = QComboBox()

        layout.addRow("Network:", self.DropdownNetwork)
        layout.addRow("Station:", self.DropdownStation)
        layout.addRow("Channel:", self.DropdownChannel)

        buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

        self.DropdownNetwork.currentIndexChanged.connect(
            self.update_stations_and_channels)
        self.update_combobox_items()
        self.resize(300, 150)

    def update_combobox_items(self):
        added_network = set()

        self.DropdownNetwork.clear()
        self.DropdownStation.clear()
        self.DropdownChannel.clear()

        for data in self.data_array:
            network_name = data["network"]
            if network_name not in added_network:
                self.DropdownNetwork.addItem(network_name)
                added_network.add(network_name)

    def update_stations_and_channels(self):
        selected_network = self.DropdownNetwork.currentText()
        selected_station = self.DropdownStation.currentText()

        available_stations = set()
        available_channels = set()

        self.DropdownStation.clear()
        self.DropdownChannel.clear()

        for data in self.data_array:
            if data["network"] == selected_network:
                available_stations.add(data["station"])
                available_channels.add(data["channel"])

        for station_name in available_stations:
            self.DropdownStation.addItem(station_name)

        for channel_name in available_channels:
            self.DropdownChannel.addItem(channel_name)


class SeismicThread(QThread):
    data_received = pyqtSignal(object)

    def __init__(self, server_address, data_array):
        super().__init__()
        self.server_address = server_address
        self.data_array = data_array

    def run(self):
        client = create_client(self.server_address, self.data_handle)
        if client:
            print("ada")
        else:
            print("netnot")
        for data in self.data_array:
            if self.server_address in data['server']:
                client.select_stream(
                    data["network"], data["station"], data["channel"])
        client.run()

    def data_handle(self, trace):
        self.data_received.emit(trace)


class LivePlotWidget(QWidget):
    def __init__(self, data_array):
        super().__init__()

        self.data_array = data_array
        self.figure, self.axes = plt.subplots(
            len(data_array), 1, figsize=(6, 6*len(data_array)), sharex=True)
        self.canvas = FigureCanvas(self.figure)

        self.merged_stream = Stream()
        self.first_trigger_skipped = False

        self.station_axes = {}
        self.data_axes = dict()
        self.last_refresh_time = UTCDateTime()

        self.setup_plots()
        self.setup_table()

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)

    def setup_plots(self):
        for i, data in enumerate(self.data_array):
            ax = self.axes[i]
            station = data['station']
            network = data['network']
            location = data['location']
            channel = data["channel"]

            key = (station, network, location, channel)
            ax.plot([], [], 'k')
            self.station_axes[key] = ax

            ax.get_yaxis().set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['top'].set_visible(False)
            ax.spines['left'].set_visible(False)
            if i != len(self.data_array) - 1:
                ax.spines['bottom'].set_visible(False)
                ax.tick_params(bottom=False)

        for ax in self.axes:
            ax.xaxis_date()
            ax.figure.autofmt_xdate()

    def setup_table(self):
        for i, data in enumerate(self.data_array):
            ax = self.axes[i]
            station = data['station'].ljust(7)
            network = data['network'].ljust(7)
            location = data['location'].ljust(5)
            channel = data["channel"].ljust(7)

            if not location:
                location = '   '

            cell_text = [[station, network, location, channel]]
            table = ax.table(cellText=cell_text, loc='left',
                             edges='open', cellLoc='center')
            table.auto_set_column_width(col=list(range(len(cell_text[0]))))

            table.auto_set_font_size(False)
            table.set_fontsize(11)
            table.scale(1, 1.5)

    def coordinate_conv(self, coor):
        derajat, menit = coor.split('-')
        derajat = float(derajat)
        menit = float(menit)
        return derajat+menit/60
    
    # Fungsi untuk menjalankan file audio di latar belakang
    def play_audio(self, file_path):
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(1)

    # Fungsi mengubah format waktu menjadi UTCDateTime
    def string_to_utc_datetime(self, date_str, origin_str):
        year = 2000 + int(date_str[:2])
        month = int(date_str[2:4])
        day = int(date_str[4:])

        hour = int(origin_str[:2])
        minute = int(origin_str[3:5])
        second = int(origin_str[6:8])
        microsecond = int(origin_str[9:]) * 10000

        return UTCDateTime(year=year, month=month, day=day, hour=hour, minute=minute, second=second, microsecond=microsecond)
    
    # Fungsi untuk mengambil nilai parameter gempa
    def eq_parameter(self, index):
        # Membaca file riwayat gempa
        with open("earthquake.txt", "r") as file:
            lines = file.readlines()

        # Mengambil data dari setiap baris
        data = []
        for line in lines:
            date = line[0:6]
            origin = line[7:17]
            lat = line[18:27]
            long = line[27:36]
            depth = line[38:43]
            mag = line[46:50]
            no = line[51:53]
            gap = line[54:57]
            dmin = line[58:62]
            rms = line[62:67]
            erh = line[69:72]
            erz = line[73:77]
            qm = line[78:80]
            data.append([date, origin, lat, long, depth, mag, no, gap, dmin, rms, erh, erz, qm])

        # Penyesuaian format
        data_gempa = pd.DataFrame(data, columns=['DATE', 'ORIGIN', 'LAT', 'LONG', 'DEPTH', 'MAG', 'NO', 'GAP', 'DMIN', 'RMS', 'ERH', 'ERZ', 'QM'])
        data_gempa['LAT'] = data_gempa['LAT'].apply(self.coordinate_conv)
        data_gempa['LONG'] = data_gempa['LONG'].apply(self.coordinate_conv)
        data_gempa['LAT'] = "-"+data_gempa['LAT']
        coordinates = ['LAT', 'LONG']
        data_gempa[coordinates] = data_gempa[coordinates].astype(float)
        data_gempa['ORIGIN'] = data_gempa['ORIGIN'].apply(lambda origin: f"{origin[:2]}:{origin[2:4]}:{origin[5:]}")
        data_gempa['ORIGIN'] = data_gempa['ORIGIN'].apply(lambda x: x.replace(' ','0'))
        data_gempa['ORIGIN TIME'] = data_gempa.apply(lambda x: self.string_to_utc_datetime(x['DATE'], x['ORIGIN']), axis=1)

        # Parameter siap diambil nilainya
        origin_time = data_gempa.iloc[index]['ORIGIN TIME']
        lat = data_gempa.iloc[index]['LAT']
        long = data_gempa.iloc[index]['LONG']
        depth = data_gempa.iloc[index]['DEPTH']

        return origin_time, lat, long, depth

    def detect_triggers(self, ax, trace):
        current_time = UTCDateTime()
        #print(current_time)

        if current_time - self.last_refresh_time >= 120:
            # start_trim_seconds = 10  # Ganti dengan jumlah detik yang ingin Anda potong
            # trace.trim(starttime=trace.stats.starttime + start_trim_seconds)
            # Clear data lama
            self.merged_stream.clear()
            self.last_refresh_time = current_time
            with open('raw_triggers.txt', 'w') as file:
                file.write("")

        self.merged_stream.append(trace)
        self.merged_stream = self.merged_stream.merge(method=1, fill_value='interpolate', interpolation_samples=-1)
        #print(self.merged_stream)

        for trace in self.merged_stream:
            station = trace.stats.station
            network = trace.stats.network
            location = trace.stats.location
            channel = trace.stats.channel
            key = (station, network, location, channel)
            ax = self.station_axes[key]

            tra = trace.copy()
            corners = 2
            freq_min = 1
            freq_max = 10
            sampling_rate = tra.stats.sampling_rate
            max_f_max = 0.9 * (sampling_rate / 2)
            freq_max = min(freq_max, max_f_max)

            tra.filter("bandpass",
                       freqmin=freq_min,
                       freqmax=freq_max,
                       corners=corners,
                       zerophase=True)

            stalta = recursive_sta_lta(tra.data, int(
                0.5 * sampling_rate), int(10 * sampling_rate))
            triggers = trigger_onset(stalta, 5, 0.3)
            
            with open('raw_triggers.txt', 'r') as file:
                isi_triggers = set(file.readlines())
            
            # Plot triggers on each trace
            for trigger in triggers:
                time_trig = tra.stats.starttime + \
                            triggers[0][0]/tra.stats.sampling_rate
                
                if str(time_trig) + '\n' not in isi_triggers:
                    with open('raw_triggers.txt', 'a') as file:
                        file.write(str(time_trig)+'\n')

                    if trigger[0] > 1:
                        #print(triggers)
                        ax.axvline(x=tra.times('matplotlib')
                               [trigger][0], color='r')
                    
                        # Pencatatan Waktu Trigger
                        station_trig = tra.stats.station
                        print("Trigger:", station_trig, time_trig)
                        trigger_output = f"{station_trig} {time_trig}"

                        with open('trigger.txt', 'r') as file:
                            isi_file = set(file.readlines())

                        if trigger_output + '\n' not in isi_file:
                            # Menambahkan waktu trigger jika belum tercatat
                            with open('trigger.txt', 'a') as file:
                                file.write(trigger_output+'\n')

                            with open('trigger.txt', 'r') as file:
                                line_count = len(file.readlines())

                            if line_count > 0:
                                df_trigger = pd.read_csv('trigger.txt', sep=' ', header=None)
                                oldest = UTCDateTime(df_trigger.iloc[0,1])
                                duration = UTCDateTime() - oldest
                                batas_waktu = 30 # detik

                                if duration < batas_waktu:
                                    # Mulai pemutaran audio di latar belakang saat trigger menyala
                                    audio_thread = threading.Thread(target=self.play_audio, args=('warning-sound-6686.mp3',))
                                    audio_thread.start()
                                
                                else:
                                    # Menghapus trigger yang melebihi batas waktu (sering terjadi pada data yang delay)
                                    with open("trigger.txt", "r") as f:
                                        lines = f.readlines()

                                    lines.pop()

                                    with open("trigger.txt", "w") as f:
                                        f.writelines(lines)

    # Fungsi membatasi trigger
    def limit_trigger(self):
        # Minimum 4 stasiun
        with open('trigger.txt', 'r') as file:
            line_count = len(file.readlines())
            
        if line_count > 0:
            df_trigger = pd.read_csv('trigger.txt', sep=' ', header=None)
            oldest = UTCDateTime(df_trigger.iloc[0,1])
            duration = UTCDateTime() - oldest
            batas_waktu = 30 # detik

            # Melakukan perhitungan parameter gempa jika data trigger minimal 4 stasiun.
            if duration < batas_waktu:
                if line_count >= 4:
                    print("Melakukan perhitungan...") # Di sini kode buat hitung parameter

                    # Cleaning the data
                    with open('input_arrival.txt', 'w') as file:
                        file.write("")

                    df_trigger['Arrival Time'] = df_trigger.iloc[:,1].apply(UTCDateTime)
                    df_trigger['Arrival Time'] = df_trigger['Arrival Time'].apply(lambda x: x.strftime("%y%m%d%H%M%S.%f")[:-4])
                    df_trigger['Parameter EP'] = 'EP'
                    df_trigger['Parameter Unknown'] = 0
                    df_trigger['Modified Name'] = df_trigger[0]
                    df_trigger['Modified Name'] = df_trigger['Modified Name'].apply(lambda x: x[:-1] if len(x) == 5 else (x + ' ' if len(x) == 3 else x))
                    df_trigger['Modified Name'] = df_trigger['Modified Name']+df_trigger['Parameter EP']

                    with open('phase_information.txt', 'w') as f:
                        for index, row in df_trigger[['Modified Name', 'Parameter Unknown', 'Arrival Time']].iterrows():
                            f.write(f"{row['Modified Name']} {row['Parameter Unknown']} {row['Arrival Time']}\n")

                    with open('phase_information.txt', 'r') as f_phase:
                        lines_phase = f_phase.readlines()

                    with open('input_arrival.txt', 'w') as f_teks1:
                        f_teks1.writelines(lines_phase)

                    file = open('input_arrival.txt', 'a')
                    file.write("""                 
                    """)
                    file.close()

                    # Merge the head and the arrival input
                    with open('input_head.txt', 'r') as f1:
                        data1 = f1.read()

                    with open('input_arrival.txt', 'r') as f2:
                        data2 = f2.read()

                    combined_data = data1 + data2

                    with open('HYPO71.INP', 'w') as output:
                        output.write(combined_data)

                    # Parameter estimation
                    system_info = platform.system()

                    if system_info == 'Linux':
                        # Definisikan perintah yang ingin dijalankan
                        perintah = """chmod +x Hypo71PC
                        ./Hypo71PC < input
                        """

                        # Jalankan perintah menggunakan subprocess
                        output = subprocess.run(perintah, shell=True, capture_output=True, text=True)
                        
                        with open('HYPO71.OUT', 'r') as source_file:
                            line = source_file.readlines()

                        # Cetak output dari perintah
                        #print("Output dari perintah:")
                        #print(output.stdout)
                    elif system_info == 'Windows':
                        # Jalankan program eksternal dengan menggunakan subprocess.Popen
                        process = subprocess.Popen('HYPO71PC.exe', stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                        
                        with open('HYPO71PC.PUN', 'r') as source_file:
                            line = source_file.readlines()

                    # Saving the earthquake history
                    if len(line) >= 2:
                        if len(line[1].strip()) > 0:
                            with open('earthquake.txt', 'w') as dest_file:
                                dest_file.write(line[1]+'\n')

                            # Suara alarm ketika gempa terdeteksi
                            audio_eq_thread = threading.Thread(target=self.play_audio, args=('earthquake_warning.mp3',))
                            audio_eq_thread.start()

                            origin_time, lat, long, depth = self.eq_parameter(-1)
                            print("EARTHQUAKE DETECTED!")
                            print("Origin Time:", origin_time)
                            print("Latitude:", lat)
                            print("Longitude:", long)
                            print("Depth:", depth)

            else:
                with open('trigger.txt', 'w') as file:
                    file.write("") # Clear file trigger

    # Fungsi baru untuk menangani plot waveform
    def plot_waveform(self, ax, trace):
        station = trace.stats.station
        network = trace.stats.network
        location = trace.stats.location
        channel = trace.stats.channel
        key = (station, network, location, channel)
        ax = self.station_axes[key]
        tra = trace.copy()
        corners = 2
        freq_min = 1
        freq_max = 10
        sampling_rate = tra.stats.sampling_rate
        max_f_max = 0.9 * (sampling_rate / 2)
        freq_max = min(freq_max, max_f_max)

        tra.data = tra.data - np.nanmean(tra.data)

        tra.taper(type='cosine', max_percentage=0.05)

        t_zpad = 1.5 * corners / freq_min
        endtime_remainder = tra.stats.endtime
        tra.trim(starttime=None, endtime=endtime_remainder +
                 t_zpad, pad=True, fill_value=0)

        # trace.trim(starttime=trace.stats.starttime + 4)
        tra.filter("bandpass",
                   freqmin=freq_min,
                   freqmax=freq_max,
                   corners=corners,
                   zerophase=True)

        tra.trim(starttime=None, endtime=endtime_remainder)

        # Plot each trace
        window_duration = 10 # minutes
        ax.plot(tra.times('matplotlib'), tra.data, 'k')
        ax.set_xlim(UTCDateTime() - 60*window_duration, UTCDateTime())

        if start:
            ax.figure.canvas.draw()

    def update_data(self, trace):
        station = trace.stats.station
        network = trace.stats.network
        location = trace.stats.location
        channel = trace.stats.channel
        key = (station, network, location, channel)
        ax = self.station_axes[key]

        trace_id = trace.id
        split_trace = trace_id.split(".")
        if split_trace[2] == "00" or split_trace[2] == "":
            self.plot_waveform(ax, trace)  # Panggil fungsi plot_waveform
            self.detect_triggers(ax, trace)  # Panggil fungsi detect_triggers
            self.limit_trigger() # Panggil fungsi membatasi trigger dan menghitung parameter gempa

class SeismicApp(QMainWindow):
    def __init__(self, data_array):
        super().__init__()

        self.central_widget = LivePlotWidget(data_array)
        self.setCentralWidget(self.central_widget)

        self.seismic_threads = []
        for server_address in ["geofon.gfz-potsdam.de"]:
            thread = SeismicThread(server_address, data_array)
            thread.data_received.connect(self.central_widget.update_data)
            self.seismic_threads.append(thread)

    def start_seismic_thread(self):
        for thread in self.seismic_threads:
            thread.start()

    def stop_seismic_thread(self):
        for thread in self.seismic_threads:
            thread.terminate()

if __name__ == "__main__":
    with open('trigger.txt', 'w') as file:
        file.write("") # Clear file trigger
    
    with open('raw_triggers.txt', 'w') as file:
        file.write("")

    app = QApplication(sys.argv)
    with open('data_array.json', 'r') as file:
        data_array = json.load(file)

    MainWindow = QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)

    MainWindow.show()

    sys.exit(app.exec_())
