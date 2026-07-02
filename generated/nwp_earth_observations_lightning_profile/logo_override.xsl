<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:fo="http://www.w3.org/1999/XSL/Format"
                version="1.0">
  <!-- Rebranding override: suppress the OGC flavor logo on the preface/legal
       page (and the cover, which is replaced separately). Coupled to the OGC
       Metanorma flavor's XSL template names. -->
  <xsl:template name="insertLogoPreface"/>
  <xsl:template name="insertLogo"/>
</xsl:stylesheet>
