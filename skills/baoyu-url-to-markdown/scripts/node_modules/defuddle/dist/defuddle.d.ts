import { DefuddleOptions, DefuddleResponse } from './types';
export declare class Defuddle {
    private readonly doc;
    private options;
    private debug;
    private _schemaOrgData;
    private _schemaOrgExtracted;
    private _metaTags;
    private _metadata;
    private _mobileStyles;
    private _smallImages;
    /**
     * Create a new Defuddle instance
     * @param doc - The document to parse
     * @param options - Options for parsing
     */
    constructor(doc: Document, options?: DefuddleOptions);
    /**
     * Lazily extract and cache schema.org data. Must be called before
     * parse() strips script tags from the document.
     */
    private getSchemaOrgData;
    /**
     * Parse the document and extract its main content
     */
    parse(): DefuddleResponse;
    /**
     * Extract text content from schema.org data (e.g. SocialMediaPosting, Article)
     */
    private _getSchemaText;
    /**
     * Remove dangerous elements and attributes from this.doc.
     * Called after parseInternal so that extractors and schema extraction
     * can still read script tags they depend on.
     */
    private _stripUnsafeElements;
    /**
     * Find the smallest DOM element whose text contains the search phrase
     * and whose word count is at least 80% of the expected count.
     * Shared by _findSchemaContentElement and _findContentBySchemaText.
     */
    private _findElementBySchemaText;
    /**
     * Find a DOM element whose text matches the schema.org text content.
     * Used when the content scorer picked the wrong element from a feed page.
     * Returns the element's inner HTML including sibling media (images, etc.)
     */
    private _findContentBySchemaText;
    private findLargestHiddenContentSelector;
    /**
     * Get the largest available src from an img element,
     * checking srcset for higher-resolution versions.
     */
    private _getLargestImageSrc;
    /**
     * Parse the document asynchronously. Checks for extractors that prefer
     * async (e.g. YouTube transcripts) before sync, then falls back to async
     * extractors if sync parse yields no content.
     */
    parseAsync(): Promise<DefuddleResponse>;
    /**
     * Fetch only async variables (e.g. transcript) without re-parsing.
     * Safe to call after parse() — uses cached schema.org data since
     * parse() strips script tags from the document.
     */
    fetchAsyncVariables(): Promise<{
        [key: string]: string;
    } | null>;
    private tryAsyncExtractor;
    /**
     * Internal parse method that does the actual work
     */
    private parseInternal;
    private countHtmlWords;
    private _log;
    private _evaluateMediaQueries;
    private applyMobileStyles;
    private removeImages;
    private removeHiddenElements;
    private removeBySelector;
    private findSmallImages;
    private removeSmallImages;
    private getElementIdentifier;
    private findMainContent;
    private findTableBasedContent;
    private findContentByScoring;
    private getElementSelector;
    private getComputedStyle;
    /**
     * Resolve relative URLs to absolute within a DOM element
     */
    private resolveRelativeUrls;
    /**
     * Flatten shadow DOM content into a cloned document.
     * Walks both trees in parallel so positional correspondence is exact.
     */
    private flattenShadowRoots;
    /**
     * Resolve React streaming SSR suspense boundaries.
     * React's streaming SSR places content in hidden divs (id="S:0") and
     * template placeholders (id="B:0") with $RC scripts to swap them.
     * Since we don't execute scripts, we perform the swap manually.
     */
    private resolveStreamedContent;
    /**
     * Replace a shadow DOM host element with a div containing its shadow content.
     * Custom elements (tag names with hyphens) would re-initialize when inserted
     * into a live DOM, recreating their shadow roots and hiding the content.
     */
    private replaceShadowHost;
    /**
     * Resolve relative URLs in an HTML string
     */
    private resolveContentUrls;
    private _extractSchemaOrgData;
    private _collectMetaTags;
    private _decodeHTMLEntities;
    /**
     * Build a DefuddleResponse from an extractor result with metadata
     */
    private buildExtractorResponse;
    /**
     * Filter extractor variables to only include custom ones
     * (exclude standard fields that are already mapped to top-level properties)
     */
    private getExtractorVariables;
    /**
     * Content-based pattern removal for elements that can't be detected by
     * CSS selectors (e.g. Tailwind/CSS-in-JS sites with non-semantic class names).
     */
    private removeByContentPattern;
    /**
     * Remove an element's following siblings, and optionally the element itself.
     */
    private removeTrailingSiblings;
}
