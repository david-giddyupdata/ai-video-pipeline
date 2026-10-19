import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {CursorPass} from './CursorPass';
import {EditPass, OverlayClip} from './EditPass';
import {EditPlan} from './plan';
import {Slides, SlidesProps} from './Slides';
import {Highlighter, HighlighterProps} from './overlays/Highlighter';
import {AvatarStage, STAGE_SAMPLE, StageProps} from './overlays/AvatarStage';
import {CtaPreview, CtaPreviewProps} from './overlays/CtaPreview';
import {SERIES_CARD_SAMPLE, SeriesCardPreview, SeriesCardProps} from './overlays/SeriesCard';
import {subscribeSample, SubscribePreview, SubscribeProps} from './overlays/SubscribeCta';
import {CHAPTER_CARD_SAMPLE, ChapterCardPreview, ChapterCardProps} from './overlays/ChapterCard';
import {CHOICE_PANEL_SAMPLE, ChoicePanelPreview, ChoicePanelProps} from './overlays/ChoicePanel';
import {MAP_PINS_SAMPLE, MapPinsPreview, MapPinsProps} from './overlays/MapPins';
import {TERM_CHIP_SAMPLE, TermChipPreview, TermChipProps} from './overlays/TermChip';
import {WORD_BUILD_SAMPLE, WordBuildPreview, WordBuildProps} from './overlays/WordBuild';
import {CursorTrack} from './track';
import {Reel, REEL_SAMPLE, ReelProps} from './overlays/Reel';

// Size and length come from the props file (--props), so each composition serves every take.
type Sized = {durationInFrames: number; fps: number; width: number; height: number};
const sized = <T extends Sized>(): CalculateMetadataFunction<T> => ({props}) => ({
  durationInFrames: props.durationInFrames, fps: props.fps, width: props.width, height: props.height,
});

const EMPTY_TRACK: CursorTrack = {video: 'raw.mp4', fps: 30, width: 1920, height: 1080, durationInFrames: 30,
  moves: [], clicks: []};

const EMPTY_SLIDES: SlidesProps = {fps: 30, width: 1920, height: 1080, durationInFrames: 30, still: 'still.jpg',
  sequence: 'opening', audio: [], slides: []};

const EMPTY_PLAN: EditPlan = {video: 'raw.mp4', fps: 30, width: 1920, height: 1080, durationInFrames: 30,
  gap_treatment: 'cut', segments: [{type: 'hold', t: 0, dur: 1, src_t: 0}], narration: [],
  cursor: {moves: [], clicks: [], style: {height_px: 48, ring_diameter_px: 88, ring_stroke_px: 5}},
  captions: {burn: true, cues: []}};

const EMPTY_HIGHLIGHTER: HighlighterProps = {durationInFrames: 30, fps: 30, width: 1920, height: 1080, still: '',
  highlights: []};

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="CursorPass" component={CursorPass} defaultProps={EMPTY_TRACK}
      calculateMetadata={sized<CursorTrack>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    <Composition id="EditPass" component={EditPass} defaultProps={EMPTY_PLAN}
      calculateMetadata={sized<EditPlan>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    <Composition id="OverlayClip" component={OverlayClip} defaultProps={{...EMPTY_PLAN, only: 'cursor'}}
      calculateMetadata={sized<EditPlan & {only?: string}>()} durationInFrames={30} fps={30} width={1920}
      height={1080} />
    <Composition id="Highlighter" component={Highlighter} defaultProps={EMPTY_HIGHLIGHTER}
      calculateMetadata={sized<HighlighterProps>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    {/* the overlay composition set (R131, R134): previews with sample props; `still` puts a frame behind them */}
    <Composition id="ChapterCard" component={ChapterCardPreview} defaultProps={CHAPTER_CARD_SAMPLE}
      calculateMetadata={sized<ChapterCardProps>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    <Composition id="TermChip" component={TermChipPreview} defaultProps={TERM_CHIP_SAMPLE}
      calculateMetadata={sized<TermChipProps>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    <Composition id="ChoicePanel" component={ChoicePanelPreview} defaultProps={CHOICE_PANEL_SAMPLE}
      calculateMetadata={sized<ChoicePanelProps>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    <Composition id="WordBuild" component={WordBuildPreview} defaultProps={WORD_BUILD_SAMPLE}
      calculateMetadata={sized<WordBuildProps>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    <Composition id="MapPins" component={MapPinsPreview} defaultProps={MAP_PINS_SAMPLE}
      calculateMetadata={sized<MapPinsProps>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    {/* the avatar's intro and outro stage (R205 to R209; pipeline/edit/stage.py) */}
    <Composition id="AvatarStage" component={AvatarStage} defaultProps={STAGE_SAMPLE}
      calculateMetadata={sized<StageProps>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    {/* R242: the series card and the subscribe animation's four variations (transparent; `still` for a background),
        and their previews over a round's stage (CtaPreview: props from the round's AvatarStage plus the piece) */}
    <Composition id="SeriesCard" component={SeriesCardPreview} defaultProps={SERIES_CARD_SAMPLE}
      calculateMetadata={sized<SeriesCardProps>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    <Composition id="SubscribeClassic" component={SubscribePreview} defaultProps={subscribeSample('classic')}
      calculateMetadata={sized<SubscribeProps>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    <Composition id="SubscribeBrand" component={SubscribePreview} defaultProps={subscribeSample('brand')}
      calculateMetadata={sized<SubscribeProps>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    <Composition id="SubscribePill" component={SubscribePreview} defaultProps={subscribeSample('pill')}
      calculateMetadata={sized<SubscribeProps>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    <Composition id="SubscribeSoft" component={SubscribePreview} defaultProps={subscribeSample('soft')}
      calculateMetadata={sized<SubscribeProps>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    <Composition id="CtaPreview" component={CtaPreview}
      defaultProps={{durationInFrames: 30, fps: 30, width: 1920, height: 1080, stage: STAGE_SAMPLE, captions: []}}
      calculateMetadata={sized<CtaPreviewProps>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    {/* R248: the highlight reel's graphics, one layer a beat (tools/reel.py) */}
    <Composition id="Reel" component={Reel} defaultProps={REEL_SAMPLE}
      calculateMetadata={sized<ReelProps>()} durationInFrames={30} fps={30} width={1920} height={1080} />
    <Composition id="Slides" component={Slides} defaultProps={EMPTY_SLIDES}
      calculateMetadata={sized<SlidesProps>()} durationInFrames={30} fps={30} width={1920} height={1080} />
  </>
);
