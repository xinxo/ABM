#//////////////////////////////////////////////////////////////////////////////
#////                                                                       ///
#//// Copyright INRO, 2016-2017.                                            ///
#//// Rights to use and modify are granted to the                           ///
#//// San Diego Association of Governments and partner agencies.            ///
#//// This copyright notice must be preserved.                              ///
#////                                                                       ///
#//// import/import_traffic_demand.py                                       ///
#////                                                                       ///
#////                                                                       ///
#////                                                                       ///
#////                                                                       ///
#//////////////////////////////////////////////////////////////////////////////

TOOLBOX_ORDER = 63


import inro.modeller as _m
import traceback as _traceback
import numpy
import omx as _omx
import os


dem_utils = _m.Modeller().module('sandag.utilities.demand')
gen_utils = _m.Modeller().module("sandag.utilities.general")


class ImportMatrices(_m.Tool(), gen_utils.Snapshot):

    external_zones = _m.Attribute(str)
    output_dir = _m.Attribute(unicode)
    num_processors = _m.Attribute(str)
    
    tool_run_msg = ""

    @_m.method(return_type=_m.UnicodeType)
    def tool_run_msg_status(self):
        return self.tool_run_msg

    def __init__(self):
        self.external_zones = "1-12"
        project_dir = os.path.dirname(_m.Modeller().desktop.project.path)
        main_dir = os.path.dirname(project_dir)
        self.output_dir = os.path.join(main_dir, "output")
        self.num_processors = "MAX-1"
        self.attributes = ["external_zones", "output_dir", "num_processors"]

    def page(self):
        pb = _m.ToolPageBuilder(self)
        pb.title = "Import auto demand and sum matrices"
        pb.description = """ 
<div style="text-align:left">    
    Imports the trip matrices generated by CT-RAMP in OMX format, and
    adds the demand from the aggregate models for the final
    trip assignments. <br>
    A total of 50 OMX files are expected, for 5 time periods
    EA, AM, MD, PM and EV, times 5 model segments for auto:
    <ul>
        <li>autoInternalExternalTrips_XX.omx</li>
        <li>autoVisitorTrips_XX.omx</li>
        <li>autoCrossBorderTrips_XX.omx</li>
        <li>autoAirportTrips_XX.omx</li>
        <li>autoTrips_XX.omx</li>
    </ul>
    Adds the aggregate demand from the commercial vehicle model, 
    external-external and external-internal to the time-of-day
    total demand matrices.
    <br>
</div>
        """
        pb.branding_text = "- SANDAG - Model"

        if self.tool_run_msg != "":
            pb.tool_run_status(self.tool_run_msg_status)
        pb.add_select_file('output_dir', 'directory',
                           title='Select output directory')
        pb.add_text_box("external_zones", title="External zones:")
        dem_utils.add_select_processors("num_processors", pb, self)
        return pb.render()

    def run(self):
        self.tool_run_msg = ""
        try:
            scenario = _m.Modeller().scenario
            self(self.output_dir, self.external_zones, self.num_processors, scenario)
            run_msg = "Tool completed"
            self.tool_run_msg = _m.PageBuilder.format_info(run_msg, escape=False)
        except Exception as error:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                error, _traceback.format_exc(error))
            raise

    @_m.logbook_trace("Create TOD auto trip tables", save_arguments=True)
    def __call__(self, output_dir, external_zones, num_processors, scenario):
        attributes = {
            "output_dir": output_dir, 
            "external_zones": external_zones, 
            "num_processors": num_processors}
        gen_utils.log_snapshot("Sum demand", str(self), attributes)

        self.scenario = scenario
        self.output_dir = output_dir
        self.external_zones = external_zones
        self.num_processors = num_processors
        self.import_traffic_trips()
        self.add_aggregate_demand()

    @_m.logbook_trace("Import CT-RAMP traffic trips from OMX")
    def import_traffic_trips(self):
        emmebank = self.scenario.emmebank
        person = self.lookup_omx("autoTrips")
        internal_external = self.lookup_omx("autoInternalExternalTrips")
        visitor = self.lookup_omx("autoVisitorTrips")
        cross_border = self.lookup_omx("autoCrossBorderTrips")
        airport = self.lookup_omx("autoAirportTrips")
        try:
            periods = ["EA", "AM", "MD", "PM", "EV"]
            for period in periods:
                with _m.logbook_trace("Period %s" % period):
                    modes =      ["SOVGP",  "SOVTOLL", "HOV2GP", "HOV2HOV", "HOV2TOLL", "HOV3GP", "HOV3HOV", "HOV3TOLL"]
                    omx_modes = ["SOV_GP", "SOV_PAY", "SR2_GP", "SR2_HOV", "SR2_PAY",  "SR3_GP", "SR3_HOV", "SR3_PAY"]
                    modes = [period + "_" + m for m in modes]
                    omx_modes = [m + "_" + period for m in omx_modes]
                    for mode, omx_mode in zip(modes, omx_modes):
                        with _m.logbook_trace("Import for mode %s" % mode):
                            matrix = emmebank.matrix("mf%s" % mode)
                            visitor_demand = visitor[period][omx_mode].read()
                            cross_border_demand = cross_border[period][omx_mode].read()
                            airport_demand = airport[period][omx_mode].read()
                            person_demand = person[period][omx_mode].read()
                            internal_external_demand = internal_external[period][omx_mode].read()
                            
                            total_ct_ramp_trips = (visitor_demand + cross_border_demand + airport_demand + person_demand + internal_external_demand)
                            matrix.set_numpy_data(total_ct_ramp_trips, self.scenario)
                            
                            self.report([
                                ("person_demand", person_demand), 
                                ("internal_external_demand", internal_external_demand), 
                                ("cross_border_demand", cross_border_demand),
                                ("airport_demand", airport_demand), 
                                ("visitor_demand", visitor_demand), 
                                ("total_ct_ramp_trips", total_ct_ramp_trips)
                            ])
                                
        finally:
            for period in periods:
                person[period].close()
                internal_external[period].close()
                visitor[period].close()
                cross_border[period].close()
                airport[period].close()

    @_m.logbook_trace('Add aggregate demand', save_arguments=True)
    def add_aggregate_demand(self):
        matrix_calc = dem_utils.MatrixCalculator(self.scenario, self.num_processors)
        periods = ["EA", "AM", "MD", "PM", "EV"]
        with matrix_calc.trace_run("Add commercial vehicle trips to auto demand"):
            for period in periods:
                matrix_calc.add("mf%s_SOVGP" % period, "mf%(p)s_SOVGP + mf%(p)s_COMVEHGP " % ({'p': period}))
                matrix_calc.add("mf%s_SOVTOLL" % period, "mf%(p)s_SOVTOLL + mf%(p)s_COMVEHGP" % ({'p': period}))

        with matrix_calc.trace_run("Add external-internal trips to auto demand"):
            modes = ["SOVGP", "SOVTOLL", "HOV2HOV", "HOV2TOLL", "HOV3HOV", "HOV3TOLL"]
            for period in periods:
                for mode in modes:
                    matrix_calc.add("mf%s_%s" % (period, mode),
                         "mf%(p)s_%(m)s + mf%(p)s_%(m)s_EIWORK + mf%(p)s_%(m)s_EINONWORK" % ({'p': period, 'm': mode}))

        # External - external faster with single-processor as number of O-D pairs is so small (12 X 12)
        matrix_calc.num_processors = 0
        with matrix_calc.trace_run("Add external-external trips to auto demand"):
            modes = ["SOVGP", "HOV2HOV", "HOV3HOV"]
            for period in periods:
                for mode in modes:
                    matrix_calc.add(
                        "mf%s_%s" % (period, mode),
                        "mf%(p)s_%(m)s + mf%(p)s_%(m)s_EETRIPS" % ({'p': period, 'm': mode}),
                        {"origins": self.external_zones, "destinations": self.external_zones})

    def lookup_omx(self, file_name):
        directory = self.output_dir
        periods = ["EA", "AM", "MD", "PM", "EV"]
        matrix_tables = {}
        for period in periods:
            file_path = os.path.join(directory, file_name + "_" + period + ".mtx")
            matrix_tables[period] = _omx.openFile(file_path, 'r')
        return matrix_tables

    def report(self, matrices):
        emmebank = self.scenario.emmebank
        text = ['<div class="preformat">']
        num_cells = len(self.scenario.zone_numbers) ** 2
        text.append("Number of O-D pairs: %s. <br>" % num_cells)
        text.append("%-25s %9s %9s %9s %13s" % ("name", "min", "max", "mean", "sum"))
        for name, data in matrices:
            stats = (name, data.min(), data.max(), data.mean(), data.sum())
            text.append("%-25s %9.4g %9.4g %9.4g %13.7g" % stats)
        text.append("</div>")
        title = 'Traffic demand summary'
        report = _m.PageBuilder(title)
        report.wrap_html('Matrix details', "<br>".join(text))
        _m.logbook_write(title, report.render())