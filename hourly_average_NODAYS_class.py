import csv
import plotly.express as px

from datetime import datetime

class HourlyPlot:

    def __init__(self, filename=''):
        '''Takes a filename parameter if used as a class, if standalone it will ask the user for a filename'''
        self.week_dict = {}
        self.plot_dict = {'hours': [], 'averages': []}

        # Are we standalone, or not?
        if __name__ == '__main__':
            self.file_name = input('Please enter a filename, leave blank for default: ')
            if len(self.file_name) == 0:
                self.file_name = 'humidity.csv'
        else:
            self.file_name = filename
            self.open_n_read()
            self.get_averages()
        

    def set_filename(self, filename=''):
        '''Sets a new filename
        OPTIONAL: filename - If not passed a filename this method will ask the user for one
        '''
        if len(filename) == 0:
            self.file_name = input('Please enter a filename: ')
        else:
            self.file_name = filename

    def open_n_read(self):
        '''Opens the csv file, and reads its contents into a dictonary'''
        with open(self.file_name, 'r') as f:
            reader = csv.reader(f)

            header_lines = next(reader)

            for row in reader:
                current_time = datetime.strptime(row[0], "%m/%d/%y %H:%M:%S")
                current_hour = current_time.hour
                if current_hour not in self.week_dict.keys():
                    self.week_dict[current_hour] = []
                
                try:
                    self.week_dict[current_hour].append(float(row[1]))
                except ValueError:
                    print(f'{current_time.strftime("%m/%d/%y %H:%M:%S")} temperature is invalid, skipping...')
        
        # Sort the dictonary in ascending order
        self.week_dict = dict(sorted(self.week_dict.items(), key=lambda item: item[0]))

    def get_averages(self):
        '''Gets the averages, puts it in a dictonary'''
        for key, value in self.week_dict.items():
            avg = sum(value) / len(value)

            self.plot_dict['hours'].append(key)
            self.plot_dict['averages'].append(round(avg, 2))

    def build_plot(self):
        '''Returns the built plot, RETURNS IT NOT SHOWS IT'''
        fig = px.line(
        self.plot_dict,
        x='hours',
        y='averages',
        template='plotly_dark',
        labels={
            'hours': "Hour (Military Time)",
            'averages': "Temperature",
        },
        title='Average Temperature between Hours',
        )

        fig.update_xaxes(nticks=24)
        fig.update_traces(mode="lines", hovertemplate=None)
        fig.update_layout(hovermode="x unified")

        return fig

if __name__ == '__main__':
    plot = HourlyPlot()
    plot.open_n_read()
    plot.get_averages()
    plot.build_plot()

    print('Jobs done')