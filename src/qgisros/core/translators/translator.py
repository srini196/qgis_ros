from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsWkbTypes
import rospy
from ..crs import PROJ4_SIMPLE
from ..helpers import featuresToQgs


class Translator(object):
    '''A base class for all translators.
    Reimplement `createLayer` to return a new QgsVectorLayer or QgsRasterLayer with the desired data provider.
    Or use one of the existing mixins: VectorTranslatorMixin or RasterTranslatorMixin.

    Reimplement `translate` to accept a ROS message and return a GeoJSON object or filename of GeoTiff.
    '''

    GeomTypes = QgsWkbTypes

    messageType = None
    dataModelType = None
    geomType = GeomTypes.Unknown

    # TODO: what are these for again?
    # @classmethod
    # def createLayer(cls, name, subscribe=False):
    #     raise NotImplementedError(str(cls))

    # @classmethod
    # def translate(msg):
    #     raise NotImplementedError()


class VectorTranslatorMixin(object):

    dataModelType = 'Vector'

    @classmethod
    def createLayer(cls, topicName, rosMessages=None, subscribe=False, keepOlderMessages=False):
        if rosMessages:
            # Features were passed in, so it's a static data layer.
            geomType = QgsWkbTypes.displayString(cls.geomType)  # Get string version of geomtype enum.
            uri = '{}?crs=PROJ4:{}'.format(geomType, PROJ4_SIMPLE)
            layer = QgsVectorLayer(uri, topicName, 'memory')

            # Convert from ROS messages to GeoJSON Features to QgsFeatures.
            features = []
            for m in rosMessages:
                features += cls.translate(m)

            qgsFeatures, fields = featuresToQgs(features)
            layer.dataProvider().addAttributes(fields)
            layer.dataProvider().addFeatures(qgsFeatures)
            layer.updateFields()  # Required, otherwise the layer will not re-read field metadata.
            return layer
        else:
            # No features, it must be a ROS topic to get data from.
            uri = '{}?type={}&index=no&subscribe={}&keepOlderMessages={}'.format(
                topicName,
                cls.messageType._type,
                subscribe,
                keepOlderMessages
            )
            layer = QgsVectorLayer(uri, topicName, 'rosvectorprovider')

            # Need to monitor when data is changed and call updateFields in order to capture the new fields
            # that are discovered on the first and possibly future messages. Without this, the layer will never
            # expose any of the field data available.
            # TODO: Find a cleaner way to signal this update and only call it when actual field changes occur.
            layer.dataChanged.connect(layer.updateFields)
            return layer


class RasterTranslatorMixin(object):

    dataModelType = 'Raster'

    @classmethod
    def createLayer(cls, topicName, rosMessages=None, **kwargs):
        '''Creates a raster layer from a ROS message.
        Unlike vector data, raster layers cannot currently be subscribed to.
        '''
        if rosMessages:
            msg = rosMessages[0]
        else:
            msg = rospy.wait_for_message(topicName, cls.messageType, 10)

        geotiffFilename = cls.translate(msg)
        layer = QgsRasterLayer(geotiffFilename, topicName)
        return layer