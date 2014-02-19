import cv
import cv2
import numpy as np
import cv_compat

from scipy.stats import tmean, scoreatpercentile
def trimmean(arr, keep_percent):
  trim_percent = (100-keep_percent)/2
  lower_limit = scoreatpercentile(arr, trim_percent)
  upper_limit = scoreatpercentile(arr, 100-trim_percent)
  return tmean(arr, limits=(lower_limit, upper_limit), inclusive=(True, True))

def make_color(x):
  brightness = np.floor(x*250)
  return (brightness, brightness, brightness)

def normalize(x):
  x = x - x.min()
  x = x/x.max()
  return x

class Flow:
  """
  Represents the optical flow between two frames.
  """

  def __init__(self, vectors, curr_frame, prev_frame):
    self.vectors = vectors
    self.curr_frame = curr_frame
    self.prev_frame = prev_frame

  @staticmethod
  def draw_flow(vis, im, flow, step=16):
    mult = 4

    w, h = cv_compat.get_dims(im)
      
    y,x = np.mgrid[step/2:h:step,step/2:w:step].reshape(2,-1)
    fx,fy = flow[y,x].T

    #meanx,meany = np.mean(flow, (0,1))
    #colorx = normalize(fx-meanx)
    #colory = normalize(fx-meany)

    #import pdb; pdb.set_trace()
    #flow_theta = np.arctan2(fx,fy) + np.pi
    #mean_theta = np.arctan2(*np.mean(flow, (0,1))) + np.pi
    #mean_theta = np.arctan2(trimmean(flow[:,:,0], 80), trimmean(flow[:,:,1], 80)) + np.pi
    #locality = normalize(np.abs((flow_theta - mean_theta) % np.pi*2))

    #local = (locality > 0.1) * 1

    #magnitudes = normalize(np.sqrt(np.square(fx) + np.square(fy)))

    #head_x,head_y = np.arctan(-np.mean(flow, (0,1)))/2.77
    # import pdb; pdb.set_trace()

    # create line endpoints
    lines = np.vstack([x,y,x+(fx*mult),y+(fy*mult)]).T.reshape(-1,2,2)
    lines = np.int32(lines)

    for pos,((x1,y1),(x2,y2)) in enumerate(lines):
      # white = strong locality/variation from mean
      #c = make_color(local.flatten()[pos])
      #cv_compat.line(vis,(x1,y1),(int(x1+np.mean(flow[:,:,0])*mult),int(y1+np.mean(flow[:,:,1])*mult)), (0,255,0), 1, cv.CV_AA)
      cv_compat.line(vis,(x1,y1),(x2,y2), (255,255,0), 1, cv.CV_AA)
      cv_compat.circle(vis,(x1,y1),1, (255,255,0), 1, cv.CV_AA)

    #cv_compat.line(vis,(100,100),(int(100+head_x*100),100),(255,0,0), 1, cv.CV_AA)
    #cv_compat.line(vis,(100,100),(100,int(100+head_y*100)),(255,0,0), 1, cv.CV_AA)

    return vis

  # I don't belong here
  def draw_good_features(self, vis):
    corners = cv2.goodFeaturesToTrack(self.curr_frame, 5, 0.4, 0)
    for corner in corners:
      x, y = [int(i) for i in corner[0]]
      cv_compat.circle(vis,(x,y),1,(0,0,255), 3, cv.CV_AA)

  def show(self, flow=True, good_features=False, text=None, display=True):
    vis = cv_compat.color_copy(self.curr_frame)
    if flow:
      self.draw_flow(vis, self.curr_frame, self.vectors)
    if good_features:
      self.draw_good_features(vis)
    if text:
      w, h = cv_compat.get_dims(vis)
      cv_compat.putText(vis, text, (10,h-10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255))

    if display:
      cv_compat.show("Optical Flow", vis)
      if cv.WaitKey(10) == 27:
        return

    return vis

class OpticalFlow:
  """
  Given a video file extracts the optical flow.
  """

  def __init__(self, path):
    self.path = path

  def _iter_frames(self, vid):
    vid_length = cv_compat.get_vid_length(vid)
    prev_frame = cv_compat.get_gray_frame(vid)
    curr_frame = cv_compat.get_gray_frame(vid)
    for i in xrange(vid_length-2):
      yield (prev_frame, curr_frame)
      prev_frame = curr_frame
      curr_frame = cv_compat.get_gray_frame(vid)

  def lucas_kanade(self):
    vid = cv.CaptureFromFile(self.path)

    first_frame = cv_compat.get_gray_frame(vid)
    velx = cv.CreateImage(cv.GetSize(first_frame), cv.IPL_DEPTH_32F, 1)
    vely = cv.CreateImage(cv.GetSize(first_frame), cv.IPL_DEPTH_32F, 1)

    for prev_frame, curr_frame in self._iter_frames(vid):
      cv.CalcOpticalFlowLK(prev_frame, curr_frame, (15,15), velx, vely)
      flow = np.dstack((np.asarray(cv.GetMat(velx)), np.asarray(cv.GetMat(vely))))
      yield Flow(flow, curr_frame, prev_frame)

  def horn_schunck(self):
    vid = cv.CaptureFromFile(self.path)

    term_crit = (cv.CV_TERMCRIT_ITER, 100, 0)

    first_frame = cv_compat.get_gray_frame(vid)
    velx = cv.CreateImage(cv.GetSize(first_frame), cv.IPL_DEPTH_32F, 1)
    vely = cv.CreateImage(cv.GetSize(first_frame), cv.IPL_DEPTH_32F, 1)

    for prev_frame, curr_frame in self._iter_frames(vid):
      cv.CalcOpticalFlowHS(prev_frame, curr_frame, False, velx, vely, 0.001, term_crit)
      flow = np.dstack((np.asarray(cv.GetMat(velx)), np.asarray(cv.GetMat(vely))))
      yield Flow(flow, curr_frame, prev_frame)

  def farneback(self):
    vid = cv2.VideoCapture(self.path)
    flags = cv2.OPTFLOW_FARNEBACK_GAUSSIAN & cv2.OPTFLOW_USE_INITIAL_FLOW
    for pos, (prev_frame, curr_frame) in enumerate(self._iter_frames(vid)):
      flow = cv2.calcOpticalFlowFarneback(prev_frame, curr_frame, 
                                          pyr_scale=0.5, levels=3, 
                                          winsize=10, iterations=1, 
                                          poly_n=5, poly_sigma=1.1, 
                                          flags=flags)
      yield Flow(flow, curr_frame, prev_frame)


if __name__ == "__main__":
  from sys import argv

  path = argv[1]
  flow_func = argv[2]
  for flow in getattr(OpticalFlow(path), flow_func)():
    flow.show(good_features=True)
