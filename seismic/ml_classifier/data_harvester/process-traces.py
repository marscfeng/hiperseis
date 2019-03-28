#script to import and process waveforms containing both P-wave and S-wave
#picks from analysts. Produces a set of files which could be used to train a
#machine-learning algorithm to recognise P and S waves from seismic traces.
from obspy.core import *
from mat4py import *
import numpy as np
import sys
import matplotlib.pyplot as plt
from scipy.signal import resample
import pickle

#ASDF database library
sys.path.append('/g/data1a/ha3/rakib/seismic/pst/passive-seismic')
from ASDFdatabase.FederatedASDFDataSet import FederatedASDFDataSet

#initialise waveform dataset
fds = FederatedASDFDataSet('/g/data/ha3/Passive/SHARED_DATA/Index/asdf_files.txt', variant='db', use_json_db=True,
                           logger=None)


#load GA's pick database
GA=loadmat("GA.mat")['GA']



#define a method to take P and S pick parameters and return the corresponding trace
def genTS(net,st,ch,loc,ptime,stime):
    
    #add some fuzz to the start and end times of the traces to avoid the neural net training itself to just pick a constant time
    starttime=ptime-(stime-ptime)/2+np.random.uniform(-(stime-ptime)/4,(stime-ptime)/4)
    endtime=stime+(stime-ptime)-np.random.uniform(-(stime-ptime)/2,(stime-ptime)/2)

    waveforms=fds.get_waveforms(net, st, loc, ch, 
                      starttime, endtime,
                      automerge=True, trace_count_threshold=10)
    if len(waveforms)==1: #discard empty streams or those containing multiple traces
        ret=waveforms[0]
    else:
        ret=None
    return ret
        




#look for individual channels with both P and S picks and build a dictionary of these
simulctr=0
allpickdict={}
for picki in range(len(GA['picks']['at'])):
    pickarr=np.asarray([GA['picks']['ne'][picki],GA['picks']['st'][picki],GA['picks']['ch'][picki],GA['picks']['ph'][picki]]).T
    pickdict={}
    if pickarr.ndim==2:
        for pickind in range(len(pickarr)):
            pick=pickarr[pickind]
            #set a key corresponding to this exact channel to check the dictionary.
            #python doesn't like using lists as dictionary keys (because the 'list' is just a pointer to some space in memory)
            #so we create a string from the list instead
            key=pick[0]+' '+pick[1]+' '+pick[2]
            if key in pickdict:
                #if the picks are for different phases
                if ('P' in pickdict[key][0] or 'P'==pick[3]) and ('S' in pickdict[key][0] or 'S'==pick[3]):
                    simulctr+=1
                    pickdict[key][0].append(pick[3])
                    pickdict[key][1].append(GA['picks']['at'][picki][pickind])
            else:
                pickdict[key]=[[pick[3]],[GA['picks']['at'][picki][pickind]]]
        for ch in pickdict:
            if len(pickdict[ch][0])>=2:
                #if the pick is multi-phase, append pick data to bigger dictionary of multi-phase picks
                if ch in allpickdict:
                    allpickdict[ch].append(pickdict[ch])
                else:
                    allpickdict[ch]=[pickdict[ch]]
print(str(len(allpickdict))+' channels detected '+str(simulctr)+' multi-phase picks.')

#process the dictionary of multi-phase picks to extract all the data required to query the waveform database
print('Processing waveforms for all multi-phase picks...')
wfctr=0
timediffs=[]
for ch in allpickdict:
    #take the string we created before and convert it back into a list of network, station, channel parameters
    idArray=ch.split()
    net=idArray[0]
    st=idArray[1]
    chloc=idArray[2].split('_')#the pick database has the channel and location as one string e.g. 'BHZ_00', or just 'BHZ' if the location is '--'.
    chan=chloc[0]
    if len(chloc)>1:
        loc=chloc[1]
    else:
        loc='--'
    for pick in allpickdict[ch]:
        if pick[0][0]=='P':
            ptimeint=[int(i) for i in pick[1][0]]
            pmsec=int((pick[1][0][-1]-ptimeint[-1])*10**6)
            ptime=UTCDateTime(*(ptimeint+[pmsec]))
            stimeint=[int(i) for i in pick[1][1]]
            smsec=int((pick[1][1][-1]-stimeint[-1])*10**6)
            stime=UTCDateTime(*(stimeint+[smsec]))
        else:
            ptimeint=[int(i) for i in pick[1][1]]
            pmsec=int((pick[1][1][-1]-ptimeint[-1])*10**6)
            ptime=UTCDateTime(*(ptimeint+[pmsec]))
            stimeint=[int(i) for i in pick[1][0]]
            smsec=int((pick[1][0][-1]-stimeint[-1])*10**6)
            stime=UTCDateTime(*(stimeint+[smsec]))
        #get a waveform to train against
        wf=genTS(net,st,chan,loc,ptime,stime)
	if not(wf is None) and len(wf)>100:#discard bad or short waveforms extracted from the database
            wfctr+=1
            #resample the waveforms to 1000 points, detrend and normalise. The extra 0.01 ensures that the resulting trace
            #does in fact have 1000 points
            wf.resample(1000.01/wf.stats.npts*wf.stats.sampling_rate)
            wf.detrend()
            wf.normalize()
	    #generate the pick distributions and normalise them
	    pdist=np.exp(-np.power(wf.times()-(ptime-wf.times("utcdatetime")[0]),2)/(0.02))#sigma is 0.1
	    sdist=np.exp(-np.power(wf.times()-(stime-wf.times("utcdatetime")[0]),2)/(0.02))
	    pdist=pdist/np.sum(pdist)
	    sdist=sdist/np.sum(sdist)
	    #plot the resulting final waveform to a file
	    outfname='wftestplot/'+'_'.join((net,st,chan,loc,ptime.ctime(),stime.ctime()))+'.png'
	    wf.plot(outfile=outfname)
	    #pickle the data and save it to a file 
	    




