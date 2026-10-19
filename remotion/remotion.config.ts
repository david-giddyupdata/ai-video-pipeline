import {Config} from '@remotion/cli/config';

// Opaque H.264 output over the recording, so JPEG frames are fine (no alpha needed).
Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(95);
Config.setOverwriteOutput(true);
Config.setConcurrency(null);
