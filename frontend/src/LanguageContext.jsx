import React, { createContext, useState, useContext, useEffect, useRef } from 'react';
import { useIsPresent } from 'framer-motion';

const translations = {
  en: {
    // Navbar
    nav_home: "Home",
    nav_draft: "Draft a GR",
    nav_chat: "NIRN.Ai Chat",
    nav_conflicts: "Conflict Detection",
    nav_search: "Search",
    nav_analyze: "Analyze",
    nav_copilot: "NIRN.Ai Chat",
    nav_ai_copilot: "NIRN.Ai Chat →",
    nav_open_menu: "Open menu",
    nav_close_menu: "Close menu",

    // Home
    home_headline: "Draft, Analyze, and Search",
    home_subheadline: "Intelligent drafting assistance, automatic conflict detection, and semantic search for Maharashtra Government Resolutions.",
    home_search_placeholder: "Search Maharashtra GRs (e.g., procurement rules, educational grants...)",
    home_gr_number_placeholder: "Enter exact GR ID (e.g., 202402281146457522)",
    home_gr_number_not_found: "GR not found in corpus. Please check the ID.",
    home_gr_number_searching: "Locating GR...",
    home_gr_number_result_title: "GR Found",
    home_try_search: "Try searching:",
    home_try_label: "Try asking:",
    home_title_1: "NIRN.Ai for ",
    home_title_2: "for Governance",
    home_title_line1: "NIRN.Ai for",
    home_title_line2: "GOVERNANCE",
    home_gr_lookup_label: "Look up by GR ID",
    home_gr_lookup_tooltip: "Enter a GR ID to look up a specific resolution directly.",
    home_stat_num: "98,950+",
    home_stat_label: "Government Resolutions",
    home_stat_sub: "Across departments. At your fingertips.",
    feat_search_title: "Semantic Search",
    feat_search_desc: "Understand natural language and find relevant GRs instantly.",
    feat_search_label: "Search now",
    feat_upload_title: "Upload & Analyze",
    feat_upload_desc: "Submit a draft GR and get AI-powered alignment checks instantly.",
    feat_upload_label: "Upload GR",
    feat_conflict_title: "Conflict Detection",
    feat_conflict_desc: "Flag clashes with existing resolutions across departments.",
    feat_conflict_label: "Explore",
    feat_template_title: "Template Checks",
    feat_template_desc: "Enforce the Manual of Office Procedure rule by rule.",
    feat_template_label: "View checks",
    home_sug_1: "GR about work from home policy",
    home_sug_2: "Leave rules for government employees",
    home_sug_3: "Latest circulars on procurement",

    // Search
    search_eyebrow: "Semantic Search",
    search_title: "Search the Corpus",
    search_sub: "Search past Government Resolutions by meaning, not keywords — a query about “late admission” finds “delayed enrolment procedure”.",
    search_placeholder: "e.g. lateral entry intake in technical institutions",
    search_searching: "Searching the corpus…",
    search_empty: "Results appear here. Try one of the suggestions on the home page.",
    search_result: "result",
    search_results: "results",
    search_view_source: "View source →",

    // Analyze
    analyze_eyebrow: "Upload & Analyze",
    analyze_title: "Draft Analysis",
    analyze_sub: "Paste a draft Government Resolution. NIRN.Ai checks it against the Manual of Office Procedure, resolves every citation, and flags conflicts with existing GRs across departments.",
    analyze_draft_title: "Draft GR",
    analyze_load_sample: "Load sample",
    analyze_label_title: "Title",
    analyze_label_dept: "Department",
    analyze_label_lang: "Language",
    analyze_label_body: "Draft text",
    analyze_btn: "Analyze draft →",
    analyze_empty: "The analysis report appears here. Load the sample draft to see it in action.",
    analyze_running: "Analyzing GR for conflicts...",
    analyze_status_clean: "Clean — ready to issue",
    analyze_status_review: "Needs review",
    analyze_status_blocked: "Blocked — resolve issues before issuing",
    analyze_card_template: "Template issues",
    analyze_card_ref: "References found",
    analyze_card_unresolved: "Unresolved refs",
    analyze_card_conflict: "Conflicts",
    analyze_sec_template: "Template compliance",
    analyze_sec_template_empty: "All Manual of Office Procedure rules passed.",
    analyze_sec_ref: "References",
    analyze_sec_ref_empty: "No GR citations found in the draft.",
    analyze_sec_conflict: "Cross-departmental conflicts",
    analyze_sec_conflict_empty: "No conflicts detected with existing GRs.",
    analyze_sec_terms: "Bilingual terminology",
    analyze_sec_terms_empty: "No terminology mappings produced.",
    analyze_fix: "Fix:",

    // Copilot
    copilot_chat_placeholder: "Ask anything about Government Resolutions...",
    copilot_clear_chat: "Clear chat",
    copilot_brief_title: "Your Brief",
    copilot_describe_label: "Describe the GR you need",
    copilot_describe_placeholder: "Describe the Government Resolution you would like to draft...",
    copilot_try_label: "Try:",
    copilot_generate_btn: "Generate GR →",
    copilot_start_over: "Start over",
    copilot_empty_title: "Your generated GR will appear here.",
    copilot_empty_desc: "Fill in the brief and click Generate.",
    copilot_loading_desc1: "Drafting your Government Resolution…",
    copilot_loading_desc2: "Referencing similar GRs from the corpus.",
    copilot_download: "Download .txt",
    copilot_download_pdf: "Download .pdf",
    copilot_dept: "Department:",
    copilot_out_lang_en: "Output Language: English",
    copilot_out_lang_mr: "Output Language: Marathi",
    copilot_analyze_draft: "Analyze this draft →",

    // Draft page
    draft_eyebrow: "AI drafting",
    draft_title: "Draft a GR",
    draft_sub: "Your intelligent assistant for drafting, querying, and auditing Government Resolutions of Maharashtra.",
    draft_brief_title: "Draft Brief & Parameters",
    draft_brief_desc: "Describe the Government Resolution you need. NIRN.Ai will handle alignment, templates, and conflict checks.",
    draft_clear_fields: "Clear Fields",
    draft_clear_confirm: "Clear all fields? This cannot be undone.",
    draft_describe_label: "Describe the Resolution Brief",
    draft_describe_placeholder: "e.g. Issue a Government Resolution regarding financial assistance of ₹25,000 for university research labs...",
    draft_try_examples: "Try Example Briefs:",
    draft_issuing_dept: "Issuing Department",
    draft_select_dept: "Select a Department",
    draft_output_lang: "Output Language",
    draft_lang_english: "English",
    draft_lang_marathi: "मराठी (Marathi)",
    draft_generate_btn: "Generate Draft GR →",
    draft_generating: "Generating GR & Running Analysis...",
    draft_stage_brief: "Brief",
    draft_stage_generate: "Generate Draft",
    draft_stage_template: "Template Validation",
    draft_stage_conflict: "Conflict Detection",
    draft_stage_reference: "Reference Tracking",
    draft_stage_ready: "Ready for Review",
    draft_stage_mobile_prefix: "Step",
    draft_stage_mobile_of: "of",
    draft_tab_mop: "MOP Rules",
    draft_tab_conflicts: "Policy Conflicts",
    draft_tab_references: "References",
    draft_tab_terminology: "Terminology",
    draft_tab_suggestions: "Suggestions",
    draft_pending: "Pending Draft",
    draft_viewer_empty_title: "Your generated Government Resolution will appear here.",
    draft_viewer_empty_desc: "Fill in the brief description on the left and click Generate Draft GR to begin the AI-assisted drafting workflow.",
    draft_viewer_loading_title: "Drafting Government Resolution...",
    draft_viewer_loading_desc: "Synthesizing retrieved GR templates, enforcing legal formatting, and performing conflict verification.",
    draft_official: "OFFICIAL DRAFT",
    draft_copy: "Copy",
    draft_copied: "Copied",
    draft_download_txt: ".txt",
    draft_download_pdf: "PDF Print",
    draft_loading_generating: "Generating Government Resolution...",
    draft_download_conflict_report: "Download Conflict Report",
    draft_download_full_conflict_report: "Download Full Conflict Report PDF",
    draft_generating_pdf: "Generating PDF...",

    // Status verbs (rotating stage indicators) — kept short so they never
    // wrap inside the narrow chat-widget bubble.
    status_verb_searching_corpus: "Searching",
    status_verb_retrieving_precedents: "Retrieving",
    status_verb_scanning_records: "Scanning GRs",
    status_verb_thinking: "Thinking",
    status_verb_drafting: "Drafting",
    status_verb_composing: "Composing",
    status_verb_validating: "Validating",
    status_verb_checking_compliance: "Checking rules",
    status_verb_contemplating: "Contemplating",
    status_verb_cross_referencing: "Cross-referencing",
    status_verb_extracting_references: "Extracting refs",

    // Chat page
    chat_eyebrow: "Ask anything",
    chat_title: "NIRN.Ai Chat",
    chat_sub: "Your intelligent assistant for querying and understanding Government Resolutions of Maharashtra.",
    chat_empty_title: "NIRN.Ai Copilot",
    chat_empty_sub: "Ask any question about Maharashtra Government Resolutions. I ground every answer in the actual GR corpus.",
    chat_starter_1: "What is the policy on lateral entry in technical colleges?",
    chat_starter_2: "Summarise the rules for government employee leave.",
    chat_starter_3: "Which department handles scholarship grievances?",
    chat_sources_used: "Sources used:",

    // Floating chat widget
    chat_widget_tooltip: "Ask NIRN.Ai",
    chat_widget_title: "NIRN.Ai",
    chat_widget_close: "Close chat",
  },
  mr: {
    // Navbar
    nav_home: "मुख्य पृष्ठ",
    nav_draft: "मसुदा तयार करा",
    nav_chat: "निर्णि.आय चॅट",
    nav_conflicts: "संघर्ष शोधन",
    nav_search: "शोध",
    nav_analyze: "विश्लेषण",
    nav_copilot: "निर्णि.आय चॅट",
    nav_ai_copilot: "निर्णि.आय चॅट →",
    nav_open_menu: "मेनू उघडा",
    nav_close_menu: "मेनू बंद करा",

    // Home
    home_headline: "मसुदा तयार करा, विश्लेषण करा आणि शोधा",
    home_subheadline: "महाराष्ट्र शासन निर्णयांसाठी बुद्धिमान मसुदा सहाय्य, स्वयंचलित संघर्ष शोध आणि अर्थपूर्ण शोध.",
    home_search_placeholder: "महाराष्ट्र शासन निर्णय शोधा (उदा., खरेदी नियम, शैक्षणिक अनुदान...)",
    home_gr_number_placeholder: "अचूक शासन निर्णय क्रमांक प्रविष्ट करा (उदा., 202402281146457522)",
    home_gr_number_not_found: "संग्रहात शासन निर्णय आढळला नाही. कृपया आयडी तपासा.",
    home_gr_number_searching: "शासन निर्णय शोधत आहे...",
    home_gr_number_result_title: "शासन निर्णय सापडला",
    home_try_search: "शोधण्याचा प्रयत्न करा:",
    home_try_label: "विचारण्याचा प्रयत्न करा:",
    home_title_1: "सुशासनासाठी ",
    home_title_2: "सुशासनासाठी",
    home_title_line1: "NIRN.Ai —",
    home_title_line2: "सुशासनासाठी",
    home_gr_lookup_label: "शासन निर्णय क्रमांकाने शोधा",
    home_gr_lookup_tooltip: "विशिष्ट शासन निर्णय थेट शोधण्यासाठी त्याचा आयडी प्रविष्ट करा.",
    home_stat_num: "९८,९५०+",
    home_stat_label: "शासन निर्णय",
    home_stat_sub: "विविध विभागांचे. तुमच्या बोटांच्या टोकावर.",
    feat_search_title: "अर्थपूर्ण शोध",
    feat_search_desc: "नैसर्गिक भाषा समजून घ्या आणि संबंधित शासन निर्णय त्वरित शोधा.",
    feat_search_label: "आता शोधा",
    feat_upload_title: "अपलोड आणि विश्लेषण",
    feat_upload_desc: "मसुदा शासन निर्णय सबमिट करा आणि त्वरित तपासणी मिळवा.",
    feat_upload_label: "शासन निर्णय अपलोड करा",
    feat_conflict_title: "संघर्ष शोध",
    feat_conflict_desc: "विभागांमधील विद्यमान शासन निर्णयांसह संघर्ष ओळखा.",
    feat_conflict_label: "अन्वेषण करा",
    feat_template_title: "टेम्पलेट तपासणी",
    feat_template_desc: "कार्यालयीन कार्यपद्धतीच्या नियमांची अंमलबजावणी करा.",
    feat_template_label: "तपासणी पहा",
    home_sug_1: "घरातून काम करण्याच्या धोरणाबाबत शासन निर्णय",
    home_sug_2: "शासकीय कर्मचाऱ्यांसाठी रजेचे नियम",
    home_sug_3: "खरेदीबाबतची नवीनतम परिपत्रके",

    // Search
    search_eyebrow: "अर्थपूर्ण शोध",
    search_title: "संग्रह शोधा",
    search_sub: "मागील शासन निर्णय अर्थानुसार शोधा, केवळ कीवर्डने नाही — 'late admission' बद्दलचा प्रश्न 'delayed enrolment procedure' शोधेल.",
    search_placeholder: "उदा. तांत्रिक संस्थांमध्ये लॅटरल एंट्री प्रवेश",
    search_searching: "संग्रहात शोधत आहे…",
    search_empty: "निकाल येथे दिसतील. मुख्य पृष्ठावरील सूचनांपैकी एक वापरून पहा.",
    search_result: "निकाल",
    search_results: "निकाल",
    search_view_source: "स्रोत पहा →",

    // Analyze
    analyze_eyebrow: "अपलोड आणि विश्लेषण",
    analyze_title: "मसुदा विश्लेषण",
    analyze_sub: "मसुदा शासन निर्णय पेस्ट करा. NIRN.Ai कार्यालयीन कार्यपद्धती मॅन्युअलनुसार तपासते, संदर्भ सोडवते आणि संघर्ष ओळखते.",
    analyze_draft_title: "मसुदा शासन निर्णय",
    analyze_load_sample: "नमुना लोड करा",
    analyze_label_title: "शीर्षक",
    analyze_label_dept: "विभाग",
    analyze_label_lang: "भाषा",
    analyze_label_body: "मसुदा मजकूर",
    analyze_btn: "मसुद्याचे विश्लेषण करा →",
    analyze_empty: "विश्लेषण अहवाल येथे दिसेल. कृतीत पाहण्यासाठी नमुना मसुदा लोड करा.",
    analyze_running: "सर्व चार तपासण्या चालवत आहे…",
    analyze_status_clean: "स्वच्छ — जारी करण्यास तयार",
    analyze_status_review: "पुनरावलोकनाची आवश्यकता आहे",
    analyze_status_blocked: "अवरोधित — जारी करण्यापूर्वी समस्या सोडवा",
    analyze_card_template: "टेम्पलेट समस्या",
    analyze_card_ref: "संदर्भ सापडले",
    analyze_card_unresolved: "न सुटलेले संदर्भ",
    analyze_card_conflict: "संघर्ष",
    analyze_sec_template: "टेम्पलेट अनुपालन",
    analyze_sec_template_empty: "सर्व कार्यालयीन कार्यपद्धती मॅन्युअल नियम उत्तीर्ण झाले.",
    analyze_sec_ref: "संदर्भ",
    analyze_sec_ref_empty: "मसुद्यात कोणतेही शासन निर्णय संदर्भ आढळले नाहीत.",
    analyze_sec_conflict: "विभागांमधील संघर्ष",
    analyze_sec_conflict_empty: "विद्यमान शासन निर्णयांसह कोणताही संघर्ष आढळला नाही.",
    analyze_sec_terms: "द्विभाषिक पारिभाषिक शब्दावली",
    analyze_sec_terms_empty: "कोणतेही पारिभाषिक मॅपिंग तयार केले नाही.",
    analyze_fix: "दुरुस्त करा:",

    // Copilot
    copilot_chat_placeholder: "शासन निर्णयांबद्दल काहीही विचारा...",
    copilot_clear_chat: "चॅट साफ करा",
    copilot_brief_title: "तुमचा मसुदा",
    copilot_describe_label: "तुमचा शासन निर्णय थोडक्यात मांडा",
    copilot_describe_placeholder: "तयार करावयाच्या शासन निर्णयाचे संक्षिप्त वर्णन येथे लिहा...",
    copilot_try_label: "प्रयत्न करा:",
    copilot_generate_btn: "शासन निर्णय तयार करा →",
    copilot_start_over: "पुन्हा सुरू करा",
    copilot_empty_title: "तुमचा शासन निर्णय येथे दिसेल.",
    copilot_empty_desc: "संक्षिप्त वर्णन भरा आणि जनरेट वर क्लिक करा.",
    copilot_loading_desc1: "तुमचा शासन निर्णय तयार करत आहे…",
    copilot_loading_desc2: "संग्रहातील समान शासन निर्णयांचा संदर्भ घेत आहे.",
    copilot_download: "डाउनलोड करा (.txt)",
    copilot_download_pdf: "डाउनलोड करा (.pdf)",
    copilot_dept: "विभाग:",
    copilot_out_lang_en: "आउटपुट भाषा: इंग्रजी",
    copilot_out_lang_mr: "आउटपुट भाषा: मराठी",
    copilot_analyze_draft: "या मसुद्याचे विश्लेषण करा →",

    // Draft page
    draft_eyebrow: "एआय मसुदा",
    draft_title: "शासन निर्णयाचा मसुदा तयार करा",
    draft_sub: "महाराष्ट्राच्या शासन निर्णयांचा मसुदा तयार करणे, चौकशी करणे आणि तपासणीसाठी तुमचा बुद्धिमान सहाय्यक.",
    draft_brief_title: "मसुदा संक्षिप्त माहिती व घटक",
    draft_brief_desc: "तुम्हाला आवश्यक असलेल्या शासन निर्णयाचे वर्णन करा. NIRN.Ai अनुरूपता, टेम्पलेट व संघर्ष तपासणी हाताळेल.",
    draft_clear_fields: "फील्ड साफ करा",
    draft_clear_confirm: "सर्व फील्ड साफ करायची आहेत का? ही क्रिया पूर्ववत करता येणार नाही.",
    draft_describe_label: "मसुद्याचे संक्षिप्त वर्णन लिहा",
    draft_describe_placeholder: "उदा. विद्यापीठ संशोधन प्रयोगशाळांसाठी ₹२५,००० आर्थिक सहाय्याबाबत शासन निर्णय जारी करा...",
    draft_try_examples: "नमुना संक्षिप्त माहिती वापरून पहा:",
    draft_issuing_dept: "जारी करणारा विभाग",
    draft_select_dept: "विभाग निवडा",
    draft_output_lang: "आउटपुट भाषा",
    draft_lang_english: "इंग्रजी (English)",
    draft_lang_marathi: "मराठी",
    draft_generate_btn: "मसुदा तयार करा →",
    draft_generating: "शासन निर्णय तयार करत आहे व विश्लेषण चालवत आहे...",
    draft_stage_brief: "संक्षिप्त माहिती",
    draft_stage_generate: "मसुदा तयार करा",
    draft_stage_template: "टेम्पलेट पडताळणी",
    draft_stage_conflict: "संघर्ष शोध",
    draft_stage_reference: "संदर्भ मागोवा",
    draft_stage_ready: "पुनरावलोकनासाठी तयार",
    draft_stage_mobile_prefix: "पायरी",
    draft_stage_mobile_of: "पैकी",
    draft_tab_mop: "कार्यपद्धती नियम",
    draft_tab_conflicts: "धोरण संघर्ष",
    draft_tab_references: "संदर्भ",
    draft_tab_terminology: "पारिभाषिक शब्दावली",
    draft_tab_suggestions: "सूचना",
    draft_pending: "मसुदा प्रलंबित",
    draft_viewer_empty_title: "तुमचा तयार केलेला शासन निर्णय येथे दिसेल.",
    draft_viewer_empty_desc: "डावीकडे संक्षिप्त वर्णन भरा आणि एआय-सहाय्यित मसुदा प्रक्रिया सुरू करण्यासाठी 'मसुदा तयार करा' वर क्लिक करा.",
    draft_viewer_loading_title: "शासन निर्णय तयार करत आहे...",
    draft_viewer_loading_desc: "पुनर्प्राप्त शासन निर्णय टेम्पलेट्सचे संश्लेषण, कायदेशीर स्वरूपन आणि संघर्ष पडताळणी करत आहे.",
    draft_official: "अधिकृत मसुदा",
    draft_copy: "कॉपी करा",
    draft_copied: "कॉपी झाले",
    draft_download_txt: ".txt डाउनलोड",
    draft_download_pdf: "पीडीएफ प्रिंट",
    draft_loading_generating: "शासन निर्णय तयार करत आहे...",
    draft_download_conflict_report: "संघर्ष अहवाल डाउनलोड करा",
    draft_download_full_conflict_report: "संपूर्ण संघर्ष अहवाल PDF डाउनलोड करा",
    draft_generating_pdf: "पीडीएफ तयार करत आहे...",

    // Status verbs (rotating stage indicators) — kept short so they never
    // wrap inside the narrow chat-widget bubble.
    status_verb_searching_corpus: "शोधत आहे",
    status_verb_retrieving_precedents: "मिळवत आहे",
    status_verb_scanning_records: "नोंदी तपासत आहे",
    status_verb_thinking: "विचार करत आहे",
    status_verb_drafting: "मसुदा तयार करत आहे",
    status_verb_composing: "रचना करत आहे",
    status_verb_validating: "पडताळणी करत आहे",
    status_verb_checking_compliance: "नियम तपासत आहे",
    status_verb_contemplating: "विचारमंथन करत आहे",
    status_verb_cross_referencing: "परस्परसंदर्भ तपासत आहे",
    status_verb_extracting_references: "संदर्भ काढत आहे",

    // Chat page
    chat_eyebrow: "काहीही विचारा",
    chat_title: "निर्णि.आय चॅट",
    chat_sub: "महाराष्ट्राच्या शासन निर्णयांबद्दल चौकशी करण्यासाठी व समजून घेण्यासाठी तुमचा बुद्धिमान सहाय्यक.",
    chat_empty_title: "निर्णि.आय कोपायलट",
    chat_empty_sub: "महाराष्ट्र शासन निर्णयांबद्दल कोणताही प्रश्न विचारा. मी प्रत्येक उत्तर वास्तविक शासन निर्णय संग्रहावर आधारित देतो.",
    chat_starter_1: "तांत्रिक महाविद्यालयांमध्ये लॅटरल एंट्रीबाबत धोरण काय आहे?",
    chat_starter_2: "शासकीय कर्मचाऱ्यांच्या रजेच्या नियमांचा सारांश द्या.",
    chat_starter_3: "शिष्यवृत्ती तक्रारी कोणता विभाग हाताळतो?",
    chat_sources_used: "वापरलेले स्रोत:",

    // Floating chat widget
    chat_widget_tooltip: "NIRN.Ai ला विचारा",
    chat_widget_title: "NIRN.Ai",
    chat_widget_close: "चॅट बंद करा",
  }
};

const LanguageContext = createContext();

export function LanguageProvider({ children }) {
  const [siteLanguage, setSiteLanguage] = useState(
    localStorage.getItem('siteLanguage') || 'en'
  );

  useEffect(() => {
    localStorage.setItem('siteLanguage', siteLanguage);
    document.documentElement.lang = siteLanguage;
  }, [siteLanguage]);

  const toggleLanguage = () => {
    setSiteLanguage(prev => prev === 'en' ? 'mr' : 'en');
  };

  const t = (key) => {
    return translations[siteLanguage][key] || translations['en'][key] || key;
  };

  return (
    <LanguageContext.Provider value={{ siteLanguage, toggleLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  let isPresent = true;
  try {
    isPresent = useIsPresent();
  } catch (e) {
    // ignore
  }

  const saved = useRef({
    siteLanguage: context.siteLanguage,
    t: context.t,
  });

  if (isPresent) {
    saved.current = {
      siteLanguage: context.siteLanguage,
      t: context.t,
    };
  }

  return {
    ...context,
    siteLanguage: saved.current.siteLanguage,
    t: saved.current.t,
  };
}
