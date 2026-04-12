/**
 * Remove permalink anchors from inside heading elements.
 * Handles symbols (#, ¶, §, 🔗), empty links, and class-based anchors.
 */
export declare function removeHeadingAnchors(element: Element): void;
export declare function isPermalinkAnchor(node: Element): boolean;
export declare const headingRules: {
    selector: string;
    element: string;
    transform: (el: Element) => Element;
}[];
