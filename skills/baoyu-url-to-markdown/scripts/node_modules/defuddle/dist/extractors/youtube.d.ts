import { BaseExtractor } from './_base';
import { ExtractorResult } from '../types/extractors';
export declare class YoutubeExtractor extends BaseExtractor {
    private videoElement;
    protected schemaOrgData: any;
    constructor(document: Document, url: string, schemaOrgData?: any);
    canExtract(): boolean;
    canExtractAsync(): boolean;
    prefersAsync(): boolean;
    extract(): ExtractorResult;
    extractAsync(): Promise<ExtractorResult>;
    private buildResult;
    private formatDescription;
    private getVideoData;
    private getChannelName;
    private getChannelNameFromDom;
    private getChannelNameFromMicrodata;
    private getChannelNameFromPlayerResponse;
    private parseInlineJson;
    private fetchTranscript;
    private fetchPlayerData;
    private fetchChapters;
    private extractChaptersFromPlayerBar;
    private extractChaptersFromEngagementPanels;
    private parseTimestamp;
    private parseTranscriptXml;
    private decodeEntities;
    private getVideoId;
    /**
     * Group raw transcript segments into readable blocks.
     * If speaker markers (>>) are present, groups by speaker turn.
     * Otherwise, groups by sentence boundaries.
     */
    private groupTranscriptSegments;
    /**
     * Group segments by speaker turns, then by sentences within each turn.
     * Each ">>" marker starts a new speaker turn (with blank line separation).
     * Within a turn, text is split at sentence boundaries for readability.
     * Tracks alternating speaker identity (0/1).
     */
    private groupBySpeaker;
    /**
     * Split turns that start with a short affirmative response (e.g. "Mhm.", "Yeah.")
     * followed by longer content. The affirmative belongs to the current speaker,
     * but the rest is likely the other speaker (missed diarization in auto-captions).
     */
    private splitAffirmativeTurns;
    /**
     * Group segments by sentence boundaries for transcripts without speaker markers.
     * Accumulates text until a segment ends with sentence-ending punctuation (.!?),
     * or until a time gap >5 seconds between segments.
     */
    private groupBySentence;
}
