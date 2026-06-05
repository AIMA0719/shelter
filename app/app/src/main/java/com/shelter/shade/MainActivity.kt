package com.shelter.shade

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.shelter.shade.ui.MapScreen
import com.shelter.shade.ui.ShadeViewModel
import com.shelter.shade.ui.theme.ShelterTheme

class MainActivity : ComponentActivity() {

    private val viewModel: ShadeViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            ShelterTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    MapScreen(viewModel = viewModel)
                }
            }
        }
    }
}
