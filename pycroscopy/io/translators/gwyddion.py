# -*- coding: utf-8 -*-
"""
Created on Fri Jun 01 15:21:46 2018

@author: Daniel Streater, Suhas Somnath
"""

from __future__ import division, print_function, absolute_import, unicode_literals
from os import path, remove
import sys
import numpy as np
import h5py

from pyUSID.io.translator import Translator, generate_dummy_main_parms
from pyUSID.io.write_utils import Dimension
from pyUSID.io.hdf_utils import create_indexed_group, write_main_dataset, write_simple_attrs, write_ind_val_dsets

# packages specific to this kind of file
from .df_utils.gsf_read import gsf_read
import gwyfile

if sys.version_info.major == 3:
    unicode = str


class GwyddionTranslator(Translator):

    def translate(self, file_path, *args, **kwargs):
        # Two kinds of files:
        # 1. Simple GSF files -> use metadata, data = gsf_read(file_path)
        # 2. Native .gwy files -> use the gwyfile package
        # I have a notebook that shows how such data can be read.
        # Create the .h5 file from the input file
        if not isinstance(file_path, (str, unicode)):
            raise TypeError('file_path should be a string!')
        if not (file_path.endswith('.gsf') or file_path.endswith('.gwy')):
            # TODO: Gwyddion is weird, it doesn't append the file extension some times. In theory, you could identify the kind of file by looking at the header (line 38 in gsf_read()). Ideally the header check should be used instead of the extension check
            # This is fine for now
            raise ValueError('file_path must have a .gsf or .gwy extension!')

        file_path = path.abspath(file_path)
        folder_path, base_name = path.split(file_path)
        base_name = base_name[:-4]
        h5_path = path.join(folder_path, base_name + '.h5')
        
        if path.exists(h5_path):
            remove(h5_path)

        h5_file = h5py.File(h5_path, 'w')

        """
        Setup the global parameters
        ---------------------------
        translator: Gywddion
        data_type: depends on file type
                    GwyddionGSF_<gsf_meta['title']>
                    or
                    GwyddionGWY_<gwy_meta['title']>
        """
        global_parms = generate_dummy_main_parms()
        global_parms['translator'] = 'Gwyddion'
        # TODO: Instead of removing ALL values in global_parms, I would recommend replacing / overwriting them as shown in the gsf_read() below

        write_simple_attrs(h5_file, global_parms)

        # Create the measurement group
        meas_grp = create_indexed_group(h5_file, 'Measurement')

        if file_path.endswith('.gsf'):
            self._translate_gsf(file_path, meas_grp)

        if file_path.endswith('gwy'):
            self._translate_gwy(file_path, meas_grp)

        return h5_path

    def _translate_gsf(self, file_path, meas_grp):
        """

        Parameters
        ----------
        file_path
        meas_grp

        For more information on the .gsf file format visit the link below -
        http://gwyddion.net/documentation/user-guide-en/gsf.html
        """
        # Read the data in from the specified file
        gsf_meta, gsf_values = gsf_read(file_path)

        # Write parameters where available specifically for sample_name
        # data_type, comments and experiment_date to file-level parms
        # Using pop, move some global parameters from gsf_meta to global_parms:
        global_parms = dict()
        global_parms['data_type'] = 'Gwyddion_GSF'
        global_parms['comments'] = gsf_meta.pop('comment', '')
        global_parms['experiment_date'] = gsf_meta.pop('date', '')

        # overwrite some parameters at the file level:
        write_simple_attrs(meas_grp.parent, global_parms)

        # Build the reference values for the ancillary position datasets:
        # TODO: Remove information from parameters once it is used meaningfully where it needs to be. Here, it is no longer necessary to save XReal anymore so we will pop (remove) it from gsf_meta
        x_offset = gsf_meta.pop('XOffset', 0)
        x_range = gsf_meta.pop('XReal', 1.0)
        # TODO: Use Numpy wherever possible instead of pure python
        x_vals = np.linspace(0, x_range, gsf_meta.pop('XRes')) + x_offset

        y_offset = gsf_meta.pop('YOffset', 0)
        y_range = gsf_meta.pop('YReal', 1.0)
        y_vals = np.linspace(0, y_range, gsf_meta.pop('YRes')) + y_offset

        # Just define the ancillary position and spectral dimensions. Do not create datasets yet
        pos_desc = [Dimension('X', gsf_meta.get('XYUnits', 'arb. units'), x_vals),
                    Dimension('Y', gsf_meta.pop('XYUnits', 'arb. units'), y_vals)]

        spec_desc = Dimension('Intensity', gsf_meta.get('ZUnits', 'arb. units'), [1])

        """
        You only need to prepare the dimensions for positions and spectroscopic. You do not need to write the 
        ancillary datasets at this point. write_main_dataset will take care of that. You only need to use 
        write_ind_val_datasets() for the cases where you may need to reuse the datasets. See the tutorial online.
        """

        # Create the channel-level group
        chan_grp = create_indexed_group(meas_grp, 'Channel')
        write_simple_attrs(chan_grp, gsf_meta)

        # Create the main dataset (and the
        two_dim_image = gsf_values
        write_main_dataset(chan_grp,
                           np.atleast_2d(np.reshape(two_dim_image,
                                                    len(pos_desc[0].values) * len(pos_desc[1].values))).transpose(),
                           'Raw_Data', gsf_meta.pop('Title', 'Unknown'), gsf_meta.pop('ZUnits', 'arb. units'),
                           pos_desc, spec_desc)

        # TODO: When passing optional arguments, you are HIGHLY recommended to specify the variable name such as aux_pos_prefix='Position_' instead of just 'Position_' (which is how you pass regulard arguments)

    def _translate_gwy(self, file_path, meas_grp):
        """

        Parameters
        ----------
        file_path
        meas_grp

        For more information on the .gwy file format visit the link below -
        http://gwyddion.net/documentation/user-guide-en/gwyfile-format.html
        """

        # Read the data in from the specified file
        gwy_data = gwyfile.load(file_path)

        # TODO: Use the Bruker translator as a reference. use the three functions below as necessary to keep the code clean and easy to read.

        # Write parameters where available specifically for sample_name
        # data_type, comments and experiment_date to file-level parms

        # write parameters common across all channels to meas_grp

        # Update existing file level parameters where appropriate

        # Prepare the list of raw_data datasets

    def _translate_image_stack(self):
        """
        Use this function to write data corresponding to a stack of scan images (most common)0
        Returns
        -------

        """
        pass

    def _translate_3d_spectroscopy(self):
        """
        Use this to translate force-maps, I-V spectroscopy etc.
        Returns
        -------

        """
        pass

    def _translate_spectra(self):
        """
        Use this to translate simple 1D data like force curves
        Returns
        -------

        """
        pass
