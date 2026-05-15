# coding: utf-8
# volumehelper.py
# Borrowed from Tim Roberts => See https://mail.python.org/pipermail/python-win32/2014-March/013080.html
from ctypes import POINTER
from ctypes.wintypes import DWORD, BOOL

import comtypes.client
from comtypes import c_float, COMMETHOD, GUID, HRESULT, IUnknown, STDMETHOD

MMDeviceApiLib = GUID("{2FDAAFA3-7523-4F66-9957-9D5E7FE698F6}")
IID_IMMDevice = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
IID_IMMDeviceEnumerator = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
IID_IMMDeviceCollection = GUID("{0BD7A1BE-7A1A-44DB-8397-CC5392387B5E}")
IID_IAudioEndpointVolume = GUID("{5CDF2C82-841E-4546-9722-0CF74078229A}")


class IMMDeviceCollection(IUnknown):
	_iid_ = GUID("{0BD7A1BE-7A1A-44DB-8397-CC5392387B5E}")


class IAudioEndpointVolume(IUnknown):
	_iid_ = GUID("{5CDF2C82-841E-4546-9722-0CF74078229A}")
	_methods_ = [
		STDMETHOD(HRESULT, "RegisterControlChangeNotify", []),
		STDMETHOD(HRESULT, "UnregisterControlChangeNotify", []),
		STDMETHOD(HRESULT, "GetChannelCount", []),
		COMMETHOD(
			[],
			HRESULT,
			"SetMasterVolumeLevel",
			(["in"], c_float, "fLevelDB"),
			(["in"], POINTER(GUID), "pguidEventContext"),
		),
		COMMETHOD(
			[],
			HRESULT,
			"SetMasterVolumeLevelScalar",
			(["in"], c_float, "fLevelDB"),
			(["in"], POINTER(GUID), "pguidEventContext"),
		),
		COMMETHOD([], HRESULT, "GetMasterVolumeLevel", (["out", "retval"], POINTER(c_float), "pfLevelDB")),
		COMMETHOD(
			[], HRESULT, "GetMasterVolumeLevelScalar", (["out", "retval"], POINTER(c_float), "pfLevelDB")
		),
		COMMETHOD(
			[],
			HRESULT,
			"SetChannelVolumeLevel",
			(["in"], DWORD, "nChannel"),
			(["in"], c_float, "fLevelDB"),
			(["in"], POINTER(GUID), "pguidEventContext"),
		),
		COMMETHOD(
			[],
			HRESULT,
			"SetChannelVolumeLevelScalar",
			(["in"], DWORD, "nChannel"),
			(["in"], c_float, "fLevelDB"),
			(["in"], POINTER(GUID), "pguidEventContext"),
		),
		COMMETHOD(
			[],
			HRESULT,
			"GetChannelVolumeLevel",
			(["in"], DWORD, "nChannel"),
			(["out", "retval"], POINTER(c_float), "pfLevelDB"),
		),
		COMMETHOD(
			[],
			HRESULT,
			"GetChannelVolumeLevelScalar",
			(["in"], DWORD, "nChannel"),
			(["out", "retval"], POINTER(c_float), "pfLevelDB"),
		),
		COMMETHOD(
			[], HRESULT, "SetMute", (["in"], BOOL, "bMute"), (["in"], POINTER(GUID), "pguidEventContext")
		),
		COMMETHOD([], HRESULT, "GetMute", (["out", "retval"], POINTER(BOOL), "pbMute")),
		COMMETHOD(
			[],
			HRESULT,
			"GetVolumeStepInfo",
			(["out", "retval"], POINTER(c_float), "pnStep"),
			(["out", "retval"], POINTER(c_float), "pnStepCount"),
		),
		COMMETHOD([], HRESULT, "VolumeStepUp", (["in"], POINTER(GUID), "pguidEventContext")),
		COMMETHOD([], HRESULT, "VolumeStepDown", (["in"], POINTER(GUID), "pguidEventContext")),
		COMMETHOD(
			[], HRESULT, "QueryHardwareSupport", (["out", "retval"], POINTER(DWORD), "pdwHardwareSupportMask")
		),
		COMMETHOD(
			[],
			HRESULT,
			"GetVolumeRange",
			(["out", "retval"], POINTER(c_float), "pfMin"),
			(["out", "retval"], POINTER(c_float), "pfMax"),
			(["out", "retval"], POINTER(c_float), "pfIncr"),
		),
	]


class IMMDevice(IUnknown):
	_iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
	_methods_ = [
		COMMETHOD(
			[],
			HRESULT,
			"Activate",
			(["in"], POINTER(GUID), "iid"),
			(["in"], DWORD, "dwClsCtx"),
			(["in"], POINTER(DWORD), "pActivationParans"),
			(["out", "retval"], POINTER(POINTER(IAudioEndpointVolume)), "ppInterface"),
		),
		STDMETHOD(HRESULT, "OpenPropertyStore", []),
		STDMETHOD(HRESULT, "GetId", []),
		STDMETHOD(HRESULT, "GetState", []),
	]


class IMMDeviceEnumerator(comtypes.IUnknown):
	_iid_ = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")

	_methods_ = [
		COMMETHOD(
			[],
			HRESULT,
			"EnumAudioEndpoints",
			(["in"], DWORD, "dataFlow"),
			(["in"], DWORD, "dwStateMask"),
			(["out", "retval"], POINTER(POINTER(IMMDeviceCollection)), "ppDevices"),
		),
		COMMETHOD(
			[],
			HRESULT,
			"GetDefaultAudioEndpoint",
			(["in"], DWORD, "dataFlow"),
			(["in"], DWORD, "role"),
			(["out", "retval"], POINTER(POINTER(IMMDevice)), "ppDevices"),
		),
	]


enumerator = comtypes.CoCreateInstance(
	CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, comtypes.CLSCTX_INPROC_SERVER
)


def get_mute():
	endpoint = enumerator.GetDefaultAudioEndpoint(0, 1)
	volume = endpoint.Activate(IID_IAudioEndpointVolume, comtypes.CLSCTX_INPROC_SERVER, None)
	return volume.GetMute()


def get_volume_level():
	endpoint = enumerator.GetDefaultAudioEndpoint(0, 1)
	volume = endpoint.Activate(IID_IAudioEndpointVolume, comtypes.CLSCTX_INPROC_SERVER, None)
	return int(round(volume.GetMasterVolumeLevelScalar() * 100))
