/**
 * Customizer controls
 *
 * @version 3.6.0
 */

( function( api, $, window, document, undefined ) {

	"use strict"

	// Bail if customizer object isn't in the DOM.
	if ( ! wp || ! wp.customize ) { 
		return; 
	}

	// Font Family Select
	api.controlConstructor['wpex-font-family'] = api.Control.extend( {

		ready: function() {

			this.container.find( 'select' ).chosen( {
				width           : '100%',
				search_contains : true
			} );

		}

	} );

	// Font Awesome Icon Select
	api.controlConstructor['wpex-fa-icon-select'] = api.Control.extend( {

		ready: function() {

			this.container.find( 'select' ).chosen( {
				width           : '100%',
				search_contains : true
			} );

		}

	} );

} ( wp.customize, jQuery, window, document ) );