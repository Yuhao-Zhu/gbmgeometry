import collections

import healpy as hp
import matplotlib.pyplot as plt
import numpy as np
from astropy.coordinates import SkyCoord
from sympy import Point3D

from gbmgeometry.gbm import GBM
from gbmgeometry.utils.array_to_cmap import array_to_cmap
from gbmgeometry.spacecraft.geometry import Ray
from gbmgeometry.spacecraft.lat import LAT, LATRadiatorMinus, LATRadiatorPlus
from gbmgeometry.spacecraft.solar_panels import SolarPanelMinus, SolarPanelPlus


class Fermi(object):
    def __init__(self, quaternion, sc_pos=None):



        """
        
        A model of Fermi that can be plotted in 3D and read healpix maps.
        

        :param quaternion: the quaternion array 
        :param sc_pos: the spacecraft position
        """

        # build fermi by creating all the components

        self._lat = LAT()

        self._lat_radiator_plus = LATRadiatorPlus()
        self._lat_radiator_minus = LATRadiatorMinus()

        self._solar_panel_plus = SolarPanelPlus()
        self._solar_panel_minus = SolarPanelMinus()

        # build a GBM

        self._gbm = GBM(quaternion, sc_pos)

        # grab the frame

        self._frame = self._gbm.n0.center.frame

        # attach the components to fermi

        self._spacecraft_components = collections.OrderedDict()

        self._spacecraft_components[self._lat.name] = self._lat

        self._spacecraft_components[self._lat_radiator_minus.name] = self._lat_radiator_minus
        self._spacecraft_components[self._lat_radiator_plus.name] = self._lat_radiator_plus

        self._spacecraft_components[self._solar_panel_plus.name] = self._solar_panel_plus
        self._spacecraft_components[self._solar_panel_minus.name] = self._solar_panel_minus

        # add lists for each detector to rays

        self._rays = collections.OrderedDict()

        for name in self._gbm.detectors.iterkeys():
            self._rays[name] = []

        self._intersection_points = None

    @property
    def spacecraft_components(self):

        return self._spacecraft_components

    @property
    def rays(self):

        return self._rays

    def add_ray(self, ray_coordinate, probability=None, color='#29FC5C'):

        """

        :param ray_coordinate: 
        :param probability: 
        :param color: 
        """
        for name, det in self._gbm.detectors.iteritems():
            ray = Ray(det, ray_coordinate, probability=probability, color=color)

            self._rays[name].append(ray)

    def compute_intersections(self, *detectors):

        self._intersection_points = collections.OrderedDict()

        all_intersections = collections.OrderedDict()

        # go thru all detectors

        if len(detectors) == 0:
            dets = self._rays.keys()

        for det_name, det in self._rays.iteritems():

            self._intersection_points[det_name] = []

            ray_dict = collections.OrderedDict()
            if det_name in dets:

                # now go through all rays

                for i, ray in enumerate(det):

                    # now all components

                    collision_info = collections.OrderedDict()

                    collision_info['surface'] = []
                    collision_info['point'] = []
                    collision_info['distance'] = []

                    for name, component in self._spacecraft_components.iteritems():

                        # intersect the volume with the rays

                        component.intersect_ray(ray)

                        plane, point, distance = component.intersection

                        current_ray_origin = Point3D(ray.ray_origin)
                        
                        if plane is not None and current_ray_origin.distance(Point3D(point)) <= current_ray_origin.distance(Point3D(ray.detector_origin)):
                            collision_info['surface'].append('%s %s' % (name, plane))
                            collision_info['point'].append(point)
                            collision_info['distance'].append(distance)

                            self._intersection_points[det_name].append(point)

                    ray_dict[i] = collision_info

                all_intersections[det_name] = ray_dict

        return all_intersections

    def plot_fermi(self, ax=None, detectors=None, with_rays=False, with_intersections=False):

        """

        :param ax: 
        :param detectors: 
        :param with_rays: 
        :param with_intersections: 
        :return: 
        """
        if ax is None:

            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')

        else:

            fig = ax.get_figure()

        if detectors is None:

            detectors = self._gbm.detectors.keys()


        else:

            for det in detectors:
                assert det in self._gbm.detectors.keys(), 'invalid detector'

        for name, component in self._spacecraft_components.iteritems():
            component.plot(ax)

        for name, det in self._gbm.detectors.iteritems():

            if name in detectors:
                ax.scatter(*det.mount_point, color='#FFC300')
                ax.text3D(*det.mount_point, s=name)

        if with_rays:

            # for all the detectors plot the rays

            for name, det in self._rays.iteritems():

                if name in detectors:

                    for ray in det:
                        ray.plot(ax)

        if with_intersections:

            # if there are intersections
            # then plot the intersection points

            if self._intersection_points is not None:

                for name, points in self._intersection_points.iteritems():
                    if name in detectors:
                        for point in points:
                            ax.scatter(*point, c='r')

        ax.set_xlabel('SCX')
        ax.set_ylabel('SCY')
        ax.set_zlabel('SCZ')

        ax.set_zlim(0, 300)
        ax.set_xlim(-400, 400)
        ax.set_ylim(-400, 400)

        ax.grid(False)
        ax.xaxis.pane.set_edgecolor('black')
        ax.yaxis.pane.set_edgecolor('black')

        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False

        return fig

    def read_healpix_map(self, healpix_map, cmap='viridis'):

        # collect the nside of the map

        nside = hp.get_nside(healpix_map)

        # get the colors of the rays based of their values

        _, colors = array_to_cmap(healpix_map, cmap=cmap, use_log=False)

        # now go thru all the points on the sphere

        for idx, val in enumerate(healpix_map):

            if val > 0:

                # if the probability is greater than 0
                # then we need to get the sky position

                ra, dec = Fermi._pix_to_sky(idx, nside)

                # mark the color

                color = colors[idx]

                # now make a point source

                ps = SkyCoord(ra, dec, unit='deg', frame='icrs')

                # transform into the fermi frame

                ps_fermi = ps.transform_to(frame=self._frame)

                self.add_ray(ps_fermi, color=color)

    @staticmethod
    def _pix_to_sky(idx, nside):
        """Convert the pixels corresponding to the input indexes to sky coordinates (RA, Dec)"""

        theta, phi = hp.pix2ang(nside, idx)

        ra = np.rad2deg(phi)
        dec = np.rad2deg(0.5 * np.pi - theta)

        return ra, dec
